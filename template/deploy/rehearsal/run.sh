#!/bin/bash
# `make rehearse-aws`: the AWS database setup and routing, locally, with no AWS. Leaves nothing behind.
set -euo pipefail
cd "$(dirname "$0")/../.."
CURL_IMAGE=curlimages/curl:8.11.1
project="$(awk '/^name:/{print $2; exit}' docker-compose.aws.yml)-rehearsal"

mkdir -p .rehearsal
workdir="$(mktemp -d "$PWD/.rehearsal/XXXXXX")"
envfile="$workdir/env"
export REHEARSAL_BOOTSTRAP="$workdir/bootstrap"
mkdir "$REHEARSAL_BOOTSTRAP"
chmod 777 "$REHEARSAL_BOOTSTRAP"  # Zitadel writes its tokens here as uid 1000
cp deploy/rehearsal/rehearsal.env "$envfile"
echo "LAGO_RSA_PRIVATE_KEY=$(openssl genrsa 2048 2>/dev/null | openssl base64 -A)" >> "$envfile"

# Compose prefers the shell's values to --env-file's, and the Makefile exports the product's .env.
# shellcheck disable=SC2046
unset $(sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' "$envfile") \
  ADMIN_CIDRS CADDY_GLOBAL_OPTIONS DB_ADMIN_USER DB_ADMIN_PASSWORD STRIPE_SECRET_KEY \
  COMPOSE_FILE COMPOSE_PROFILES COMPOSE_PROJECT_NAME

compose() {
  docker compose -p "$project" --env-file "$envfile" \
    -f docker-compose.aws.yml -f deploy/rehearsal/docker-compose.rehearsal.yml "$@"
}
remove_stack() { compose --profile setup down -v --remove-orphans >/dev/null 2>&1 || true; }
cleanup() { remove_stack; rm -rf "$workdir"; rmdir .rehearsal 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 1' INT TERM
fail() { echo "REHEARSAL FAILED: $1" >&2; compose --profile setup logs --tail=60 >&2 || true; exit 1; }

remove_stack  # an earlier run that was killed outright
compose up -d --wait db redis || fail "the stand-in database or Redis didn't start"

psql_as() {
  compose exec -T -e PGPASSWORD="$2" -e PGSSLMODE=require db psql -q -v ON_ERROR_STOP=1 -h db -U "$1" "${@:3}"
}

echo "== stand-in for the RDS admin, and TLS is required"
psql_as postgres rehearsal-superuser -d postgres \
  -c "CREATE ROLE dbadmin LOGIN PASSWORD 'rehearsal-admin' CREATEDB CREATEROLE;"
if compose exec -T -e PGPASSWORD=rehearsal-superuser -e PGSSLMODE=disable db \
  psql -h db -U postgres -d postgres -Atc "SELECT 1" >/dev/null 2>&1; then
  fail "the stand-in accepted a connection without TLS"
fi

echo "== db-init.sql: roles and databases as the non-superuser admin"
sed '/^\\connect lago/,$d' deploy/db-init.sql | psql_as dbadmin rehearsal-admin -d postgres \
  -v app_password=rehearsal-app -v lago_password=rehearsal-lago

echo "== db-init.sql, all of it, twice (LIMIT: as the stand-in superuser, because pg_partman isn't a trusted extension here; on RDS dbadmin runs it as rds_superuser)"
for _ in 1 2; do
  psql_as postgres rehearsal-superuser -d postgres \
    -v app_password=rehearsal-app -v lago_password=rehearsal-lago < deploy/db-init.sql
done

echo "== Zitadel init as the non-superuser admin"
DB_ADMIN_PASSWORD=rehearsal-admin compose --profile setup run --rm zitadel-init \
  || fail "zitadel-init doesn't work with a non-superuser admin over TLS"

echo "== start Zitadel"
compose up -d --wait --wait-timeout 300 zitadel-api || fail "Zitadel didn't become healthy"
for pat in admin.pat login-client.pat; do
  [ -s "$REHEARSAL_BOOTSTRAP/$pat" ] || fail "Zitadel didn't write $pat"
done

echo "== start Lago, the login and Caddy"
compose up -d --wait --wait-timeout 300 lago-api lago-pdf || fail "Lago didn't become healthy"
compose up -d --no-deps lago-worker lago-clock lago-front zitadel-login caddy \
  || fail "the rest of the stack didn't start"

echo "== Lago created its partitions"
count="$(psql_as lago rehearsal-lago -d lago -Atc "SELECT count(*) FROM partman.part_config;")"
[ "$count" -ge 1 ] || fail "partman.part_config is empty: Lago skipped partitioning"
partitions="$(psql_as lago rehearsal-lago -d lago -Atc \
  "SELECT count(*) FROM pg_inherits WHERE inhparent = 'public.enriched_events'::regclass;")"
[ "$partitions" -ge 1 ] || fail "enriched_events has no partitions"
echo "part_config rows: $count; enriched_events partitions: $partitions"

echo "== Lago's migrations run again and change nothing, as on every later start"
compose run --rm --no-deps lago-migrate >/dev/null 2>&1 || fail "lago-migrate failed on a migrated database"

echo "== routing"
network="${project}_default"
caddy_ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$network\").IPAddress}}" "$(compose ps -q caddy)")"
# Caddy picks a certificate by SNI, so the name has to resolve, not just appear in a Host header.
status() {
  local url_host="$1" path="$2" codes
  shift 2
  # curl writes a code for each try, so the answer is the last three characters. It retries while Caddy gets its certificate.
  codes="$(docker run --rm --network "$network" "$CURL_IMAGE" -sk -o /dev/null -w '%{http_code}' --max-time 20 \
    --retry 15 --retry-all-errors --retry-delay 2 --resolve "$url_host:443:$caddy_ip" "$@" "https://$url_host$path" || true)"
  echo "${codes: -3}"
}
check() {
  local got
  got="$(status "$@")"
  [ "$got" = "$3" ] || fail "https://$1$2 answered '$got', expected $3"
  echo "https://$1$2 -> $got"
}
d=rehearsal.localhost
check "lago.$d" / 403
check "lago-api.$d" /api/v1/plans 403
webhook="$(status "lago-api.$d" /webhooks/stripe/none)"
case "$webhook" in
  403|000|502|503|504) fail "Lago's webhooks answered '$webhook': they should reach Lago" ;;
esac
echo "https://lago-api.$d/webhooks/stripe/none -> $webhook (from Lago)"
check "auth.$d" /debug/ready 200
check "auth.$d" /ui/v2/login/healthy 200

echo "== routing for addresses on the admin list"
subnet="$(docker network inspect -f '{{(index .IPAM.Config 0).Subnet}}' "$network")"
ADMIN_CIDRS="$subnet" compose up -d --no-deps caddy >/dev/null || fail "Caddy didn't restart"
caddy_ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$network\").IPAddress}}" "$(compose ps -q caddy)")"
check "lago.$d" / 200
check "lago-api.$d" /api/v1/plans 401
# LAGO_ORG_API_KEY reached the database: the key opens the API.
got="$(status "lago-api.$d" /api/v1/plans -H "Authorization: Bearer rehearsal-lago-key")"
[ "$got" = 200 ] || fail "Lago's seeded API key answered '$got', expected 200"
echo "https://lago-api.$d/api/v1/plans with the API key -> $got"

echo "== everything is still running"
running="$(compose ps --status running --services)"
for service in db redis caddy zitadel-api zitadel-login lago-api lago-worker lago-clock lago-front lago-pdf; do
  printf '%s\n' "$running" | grep -qx "$service" || fail "$service isn't running"
done

echo "== memory, to confirm the server size (idle; backend and jobs aren't running: they have no image here)"
# shellcheck disable=SC2046
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' $(compose ps -q) | sed "s/^$project-//" | awk '
  { v = $2 + 0; if ($2 ~ /GiB/) v *= 1024; else if ($2 ~ /KiB/) v /= 1024
    printf "%-18s %8.0f MiB\n", $1, v; total += v }
  END { printf "%-18s %8.0f MiB, including the stand-in database, which is RDS on AWS\n", "total", total }'
echo "LIMITS: no AWS, no RDS, no browser sign-in, email, S3 or real certificates; db-init.sql's pg_partman part ran as a superuser."
echo "REHEARSAL PASSED"
