#!/bin/bash
# Runs at boot and from first-run.sh. Renders .env from AWS, restores Zitadel's tokens, and starts
# the stack if first-run.sh has already happened. Safe to run again.
export HOME="${HOME:-/root}"
export PATH="$PATH:/usr/local/bin"
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
source "${APP_ENV_FILE:-/etc/app.env}"
export AWS_REGION
cd "$APP_DIR"

secret() { aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text; }
param() { aws ssm get-parameter --name "$1" --query Parameter.Value --output text; }
as_env() { jq -r 'to_entries[] | "\(.key)=\(.value)"'; }

umask 077
{
  secret "$SLUG/app" | as_env
  param "/$SLUG/config" | as_env
  echo "BACKEND_TAG=$(param "/$SLUG/tags/backend")"
  echo "JOBS_TAG=$(param "/$SLUG/tags/jobs")"
  echo "DEPLOY_TARGET=aws"
} > .env.new
mv .env.new .env
chmod 600 .env
umask 022

mkdir -p .bootstrap/zitadel .bootstrap/backend
tokens="$(secret "$SLUG/bootstrap" 2>/dev/null || echo '{}')"
if [ "$(echo "$tokens" | jq -r '.admin_pat // empty')" != "" ]; then
  echo "$tokens" | jq -r .admin_pat > .bootstrap/zitadel/admin.pat
  echo "$tokens" | jq -r .login_client_pat > .bootstrap/zitadel/login-client.pat
  echo "$tokens" | jq -r .backend_pat > .bootstrap/backend/backend.pat
  echo "$tokens" | jq -r .ids_env > .bootstrap/ids.env
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
