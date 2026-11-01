# Local development. `make env` once, paste the Stripe test key into .env, then `make up` and
# `make bootstrap`. `make check` needs only Postgres (`make up`, or TEST_DATABASE_URL).
-include .env
export

# Zitadel writes its PATs into .bootstrap/zitadel as this user, so the host can read them.
export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)
POSTGRES_PORT ?= 5432
TEST_DATABASE_URL ?= postgresql+psycopg://app:app@127.0.0.1:$(POSTGRES_PORT)/app_test

.PHONY: env up down reset logs bootstrap brand sync-plans migrate doctor check e2e

env:
	cd scripts && uv run python make_env.py

up:
	@test -f .env || { echo "no .env: run 'make env' first"; exit 1; }
	mkdir -p .bootstrap/zitadel .bootstrap/backend
	docker compose up -d --build

down:
	docker compose down

# Deletes every local database, bucket and token; `make up && make bootstrap` start from scratch.
reset:
	docker compose down -v
	rm -rf .bootstrap

logs:
	docker compose logs -f --tail=100

bootstrap:
	cd scripts && uv run python -u bootstrap.py

brand:
	cd scripts && uv run python brand.py

sync-plans:
	docker compose exec -T backend uv run --no-dev python -m app.billing.sync

migrate:
	docker compose exec -T backend uv run --no-dev alembic upgrade head

doctor:
	cd scripts && uv run python doctor.py

check:
	cd backend && uv run ruff check . && uv run mypy && TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest -q
	cd jobs && uv run ruff check . && uv run mypy && uv run pytest -q
	cd scripts && uv run ruff check . && uv run mypy && uv run pytest -q
	cd frontend && npm ci --no-audit --no-fund && npm run lint && npm run typecheck && npm test && npm run build
	if [ -d .claude/hooks ]; then cd .claude/hooks && uv run --no-project --with pytest pytest -q; fi

e2e:
	cd e2e && npm ci --no-audit --no-fund && npx playwright install --with-deps chromium && npx playwright test
