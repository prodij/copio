#!/bin/bash
# `make infra-bootstrap` runs this on the server. Safe to run again: each step looks before it creates.
export HOME="${HOME:-/root}"
export PATH="$PATH:/usr/local/bin"
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
source "${APP_ENV_FILE:-/etc/app.env}" || exit 1
export AWS_REGION COMPOSE_FILE=docker-compose.aws.yml
cd "$APP_DIR"

"$APP_DIR/deploy/start.sh"

val() { { grep "^$1=" .env || true; } | cut -d= -f2-; }
DB_ADMIN_PASSWORD="$(aws secretsmanager get-secret-value --secret-id "$(val DB_ADMIN_SECRET_ARN)" \
  --query SecretString --output text | jq -er .password)"
export DB_ADMIN_PASSWORD

echo "== databases"
docker run --rm -i -e PGPASSWORD="$DB_ADMIN_PASSWORD" -e PGSSLMODE=require postgres:15-alpine \
  psql -v ON_ERROR_STOP=1 -h "$(val DB_HOST)" -U dbadmin -d postgres \
  -v app_password="$(val APP_DB_PASSWORD)" -v lago_password="$(val LAGO_DB_PASSWORD)" < deploy/db-init.sql

echo "== Zitadel's database"
docker compose --profile setup run --rm zitadel-init
unset DB_ADMIN_PASSWORD

echo "== stack"
docker compose pull --quiet
docker compose up -d

echo "== bootstrap"
DOMAIN="$(val DOMAIN)"
export DEPLOY_TARGET=aws SLUG DOMAIN
LAGO_API_KEY="$(val LAGO_API_KEY)"
LAGO_ORG_USER_PASSWORD="$(val LAGO_ORG_USER_PASSWORD)"
STRIPE_SECRET_KEY="$(val STRIPE_SECRET_KEY)"
export LAGO_API_KEY LAGO_ORG_USER_PASSWORD STRIPE_SECRET_KEY
export LAGO_ORG_USER_EMAIL="admin@$DOMAIN"
cd scripts
uv run python -u bootstrap.py

echo "== restart with the saved ids and tokens"
cd "$APP_DIR"
docker compose up -d --force-recreate backend jobs
