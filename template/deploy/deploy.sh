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

# One deploy at a time. macOS (tests) has no flock, so skip it there.
if command -v flock > /dev/null 2>&1; then
  exec 9>"$APP_DIR/.deploy.lock" || exit 1
  flock -w 600 9 || { echo "deploy: another deploy is still running" >&2; exit 1; }
fi

source "${APP_ENV_FILE:-/etc/app.env}" || exit 1
export AWS_REGION COMPOSE_FILE=docker-compose.aws.yml
cd "$APP_DIR" || exit 1

set_tag() { sed -i.bak "s/^$tag_key=.*/$tag_key=$1/" .env && rm -f .env.bak; }
previous="$(grep "^$tag_key=" .env | cut -d= -f2)"
if [ -z "$previous" ]; then
  echo "deploy: .env has no $tag_key, so there is nothing to roll back to" >&2
  exit 1
fi

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

if ! docker compose up -d "$service"; then
  echo "deploy: could not start $service:$tag, going back to $previous" >&2
  set_tag "$previous"
  if ! docker compose up -d "$service"; then
    echo "deploy: the restart of $service:$previous also failed, the service may be down" >&2
  fi
  exit 1
fi

healthy() {
  if [ "$service" = backend ]; then
    curl -fsS -m 5 http://127.0.0.1:8000/health > /dev/null
  else
    docker compose ps --status running --services | grep -qx jobs
  fi
}

# The backend answers once. Jobs has no port, so it must stay running for 5 polls in a row.
need=1
[ "$service" = jobs ] && need=5
streak=0
for _ in $(seq 1 30); do
  if healthy; then
    streak=$((streak + 1))
  else
    streak=0
  fi
  if [ "$streak" -ge "$need" ]; then
    recorded=0
    for _ in 1 2 3; do
      if aws ssm put-parameter --name "/$SLUG/tags/$service" --value "$tag" --type String --overwrite > /dev/null; then
        recorded=1
        break
      fi
      sleep 2
    done
    if [ "$recorded" = 0 ]; then
      echo "deploy: $service:$tag is deployed but not recorded in SSM; a reboot would go back to the old tag" >&2
      exit 1
    fi
    echo "deploy: $service is on $tag"
    exit 0
  fi
  sleep 2
done

echo "deploy: $service:$tag failed its health check, going back to $previous" >&2
set_tag "$previous"
if ! docker compose up -d "$service"; then
  echo "deploy: the restart of $service:$previous also failed, the service may be down" >&2
fi
exit 1
