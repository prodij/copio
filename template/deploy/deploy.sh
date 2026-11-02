#!/bin/bash
# deploy.sh <backend|jobs> <tag>. Run by CI through SSM. Exit 2 refused, 1 failed and rolled back.
export HOME="${HOME:-/root}"
export PATH="$PATH:/usr/local/bin"
set -uo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
service="${1:-}"
tag="${2:-}"

case "$service" in
  backend) tag_key=BACKEND_TAG ;;
  jobs) tag_key=JOBS_TAG ;;
  *) echo "deploy: unknown service '$service'" >&2; exit 2 ;;
esac
if ! [[ "$tag" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "deploy: '$tag' is not a commit tag" >&2
  exit 2
fi

source "${APP_ENV_FILE:-/etc/app.env}"
export AWS_REGION COMPOSE_FILE=docker-compose.aws.yml
cd "$APP_DIR" || exit 1

set_tag() { sed -i.bak "s/^$tag_key=.*/$tag_key=$1/" .env && rm -f .env.bak; }
previous="$(grep "^$tag_key=" .env | cut -d= -f2)"

registry="$(grep '^ECR_REGISTRY=' .env | cut -d= -f2)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry" || exit 1

set_tag "$tag"
if ! docker compose pull --quiet "$service"; then
  echo "deploy: could not pull $service:$tag" >&2
  set_tag "$previous"
  exit 1
fi

if [ "$service" = backend ]; then
  if ! docker compose run --rm --no-deps backend uv run --no-dev alembic upgrade head; then
    echo "deploy: migration failed, the previous version keeps running" >&2
    set_tag "$previous"
    exit 1
  fi
fi

docker compose up -d "$service"

healthy() {
  if [ "$service" = backend ]; then
    curl -fsS -m 5 http://127.0.0.1:8000/health > /dev/null
  else
    docker compose ps --status running --services | grep -qx jobs
  fi
}

for _ in $(seq 1 30); do
  if healthy; then
    aws ssm put-parameter --name "/$SLUG/tags/$service" --value "$tag" --type String --overwrite > /dev/null
    echo "deploy: $service is on $tag"
    exit 0
  fi
  sleep 2
done

echo "deploy: $service:$tag failed its health check, going back to $previous" >&2
set_tag "$previous"
docker compose up -d "$service"
exit 1
