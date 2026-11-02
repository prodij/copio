# Local development. `make env` once, then `make up` and `make bootstrap`. The Stripe test key in .env
# is optional; add it any time and re-run `make bootstrap`. BILLING_MODE=mock is mock payment (see README). `make check` needs only Postgres (`make up`,
# or TEST_DATABASE_URL).
-include .env
export
# Secrets only the containers need (Compose reads .env itself). Keep them out of every host
# process make starts: Vite exposes any ZITADEL_* variable to the browser bundle.
unexport ZITADEL_MASTERKEY ZITADEL_ADMIN_PASSWORD LOGIN_SESSION_COOKIE_SECRET SECRET_KEY_BASE \
  LAGO_RSA_PRIVATE_KEY LAGO_ENCRYPTION_PRIMARY_KEY LAGO_ENCRYPTION_DETERMINISTIC_KEY \
  LAGO_ENCRYPTION_KEY_DERIVATION_SALT S3_ACCESS_KEY S3_SECRET_KEY
# Secrets the host scripts need, exported only to the targets that run them (not check, e2e, npm).
unexport STRIPE_SECRET_KEY LAGO_API_KEY LAGO_ORG_USER_PASSWORD BILLING_MODE APP_ENV
bootstrap: export STRIPE_SECRET_KEY := $(STRIPE_SECRET_KEY)
bootstrap: export BILLING_MODE := $(BILLING_MODE)
bootstrap: export APP_ENV := $(APP_ENV)
bootstrap: export LAGO_API_KEY := $(LAGO_API_KEY)
bootstrap brand: export LAGO_ORG_USER_PASSWORD := $(LAGO_ORG_USER_PASSWORD)
# The e2e tests need to know whether there is a key, never the key itself.
# Blank or `""` in .env counts as no key, as in scripts/bootstrap.py. Make keeps quotes; Compose doesn't.
e2e: export STRIPE_CONFIGURED := $(if $(strip $(subst ",,$(subst ',,$(STRIPE_SECRET_KEY)))),1,)
e2e: export MOCK_PAYMENT := $(if $(filter mock,$(subst ",,$(subst ',,$(BILLING_MODE)))),1,)

# Zitadel writes its PATs into .bootstrap/zitadel as this user, so the host can read them.
export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)
POSTGRES_PORT ?= 5432
TEST_DATABASE_URL ?= postgresql+psycopg://app:app@127.0.0.1:$(POSTGRES_PORT)/app_test

.PHONY: env up down reset logs bootstrap brand sync-plans migrate doctor check check-generated e2e regen

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

# Only a lock that doesn't match package.json is rewritten: npm install also adds entries an in-step lock can do without.
NPM_RELOCK = npm ci --dry-run --no-audit --no-fund >/dev/null 2>&1 || npm install --package-lock-only --no-audit --no-fund

# After `copier update`, once conflicts are resolved: rebuilds what comes from other files.
regen:
	cd scripts && uv run python brand.py --css-only && uv lock
	cd backend && uv lock && uv run python -m app.export_openapi
	cd jobs && uv lock
	cd frontend && $(NPM_RELOCK) && npm ci --no-audit --no-fund && npm run gen:api
	cd e2e && $(NPM_RELOCK)

# Generated files that no longer match their sources. Needs no stack, and changes nothing in the tree.
check-generated:
	cd scripts && uv run python brand.py --check
	cd backend && uv run python -m app.export_openapi --check
	@cd frontend && tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	  { npx --no-install openapi-typescript ../backend/openapi.json -o "$$tmp/schema.d.ts" >/dev/null || \
	    { echo "could not compare frontend/src/api/schema.d.ts: openapi-typescript failed. Is frontend/node_modules missing? Run \`cd frontend && npm ci\`."; exit 1; }; } && \
	  { cmp -s "$$tmp/schema.d.ts" src/api/schema.d.ts || \
	    { echo "out of date with backend/openapi.json: frontend/src/api/schema.d.ts. Run \`make regen\`."; exit 1; }; }

check:
	cd backend && uv run ruff check . && uv run mypy && TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest -q
	cd jobs && uv run ruff check . && uv run mypy && uv run pytest -q
	cd scripts && uv run ruff check . && uv run mypy && uv run pytest -q
	cd frontend && npm ci --no-audit --no-fund
	$(MAKE) --no-print-directory check-generated
	cd frontend && npm run lint && npm run typecheck && npm test && npm run build
	if [ -d .claude/hooks ]; then cd .claude/hooks && uv run --no-project --with pytest pytest -q; fi

e2e:
	cd e2e && npm ci --no-audit --no-fund && npx playwright install --with-deps chromium && npx playwright test
	@if [ -n "$$MOCK_PAYMENT" ]; then echo "MOCK PAYMENT run: the Stripe payment test did not run. A mock payment pass is not a Stripe pass."; fi
