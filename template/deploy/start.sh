#!/bin/bash
# Runs at boot and from first-run.sh. Renders .env from AWS, restores Zitadel's tokens, and starts
# the stack if first-run.sh has already happened. Safe to run again.
export HOME="${HOME:-/root}"
export PATH="$PATH:/usr/local/bin"
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
source "${APP_ENV_FILE:-/etc/app.env}" || exit 1
export AWS_REGION
cd "$APP_DIR"

# Prints the secret. Exit 44 when it has no value yet (ResourceNotFoundException); any other
# failure prints the AWS error to stderr and exits 1. Never prints the value on failure.
secret() {
  local out err
  err="$(mktemp)"
  if out="$(aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text 2>"$err")"; then
    rm -f "$err"
    printf '%s\n' "$out"
    return 0
  fi
  if grep -q ResourceNotFoundException "$err"; then
    rm -f "$err"
    return 44
  fi
  echo "start: could not read secret $1:" >&2
  cat "$err" >&2
  rm -f "$err"
  return 1
}
param() { aws ssm get-parameter --name "$1" --query Parameter.Value --output text; }
as_env() { jq -r 'to_entries[] | "\(.key)=\(.value)"'; }

# Read everything before writing anything, so a failure leaves the last good .env alone.
status=0
app_secret="$(secret "$SLUG/app")" || status=$?
if [ "$status" = 44 ]; then
  echo "start: $SLUG/app has no values yet: run make infra-secrets first" >&2
  exit 44
elif [ "$status" != 0 ]; then
  exit "$status"
fi
config="$(param "/$SLUG/config")"
backend_tag="$(param "/$SLUG/tags/backend")"
jobs_tag="$(param "/$SLUG/tags/jobs")"
app_env="$(echo "$app_secret" | as_env)"
config_env="$(echo "$config" | as_env)"
if [ -z "$backend_tag" ] || [ -z "$jobs_tag" ]; then
  echo "start: an image tag in SSM is empty" >&2
  exit 1
fi

umask 077
{
  echo "$app_env"
  echo "$config_env"
  echo "BACKEND_TAG=$backend_tag"
  echo "JOBS_TAG=$jobs_tag"
  echo "DEPLOY_TARGET=aws"
} > .env.new
mv .env.new .env
chmod 600 .env
umask 022

mkdir -p .bootstrap/zitadel .bootstrap/backend
status=0
tokens="$(secret "$SLUG/bootstrap")" || status=$?
if [ "$status" = 44 ]; then
  tokens='{}'
elif [ "$status" != 0 ]; then
  exit 1
fi
if ! echo "$tokens" | jq -e . > /dev/null 2>&1; then
  echo "start: the bootstrap secret is not valid JSON" >&2
  exit 1
fi
if [ "$(echo "$tokens" | jq -r '.admin_pat // empty')" != "" ]; then
  admin_pat="$(echo "$tokens" | jq -er .admin_pat)"
  login_client_pat="$(echo "$tokens" | jq -er .login_client_pat)"
  backend_pat="$(echo "$tokens" | jq -er .backend_pat)"
  ids_env="$(echo "$tokens" | jq -er .ids_env)"
  echo "$admin_pat" > .bootstrap/zitadel/admin.pat
  echo "$login_client_pat" > .bootstrap/zitadel/login-client.pat
  echo "$backend_pat" > .bootstrap/backend/backend.pat
  echo "$ids_env" > .bootstrap/ids.env
  bootstrapped=1
else
  bootstrapped=0
fi
chown -R 1000:1000 .bootstrap 2>/dev/null || true

registry="$(grep '^ECR_REGISTRY=' .env | cut -d= -f2)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"

export COMPOSE_FILE=docker-compose.aws.yml
if [ "$bootstrapped" = 1 ]; then
  docker compose pull --quiet
  docker compose up -d
else
  echo "start: no saved tokens yet, so the stack waits for make infra-bootstrap"
fi
