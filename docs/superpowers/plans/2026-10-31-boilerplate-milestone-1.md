# Copio Boilerplate Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `prodij/copio` into a Copier template whose generated product runs locally on Docker Compose with branded Zitadel sign-in, workspaces, Lago + Stripe (test mode) billing and plan-based feature access, proven by one end-to-end test.

**Architecture:** The repo root holds `copier.yml`, a `template/` directory that becomes each product, and `tests/` that generate a product and test it. A generated product has a FastAPI backend (modules `auth`, `workspaces`, `billing`, `access`) on Postgres, a React SPA, Lambda-shaped Python jobs, and a `brand/` folder; Zitadel and Lago run unmodified in Compose and the backend is the only component that calls them.

**Tech Stack:** Copier 9.19 · Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, httpx, PyJWT, PyYAML, boto3, croniter, pytest, respx · React 19, Vite, TypeScript, Tailwind 4, shadcn/ui (Base UI, style `base-vega`), oidc-client-ts, openapi-typescript + openapi-fetch, Vitest, Testing Library, Playwright · Zitadel v4.20.0 · Lago v1.55.0 · Stripe CLI 1.55.6 · Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md`

## Global Constraints

- Personal project. No code is copied from NG or Skylit repositories; everything is written fresh (spec D12).
- `prodij/copio` is public: no secret values in git, ever. `.env` is git-ignored; `.env.example` has names only. The template self-test fails on anything resembling a key.
- Zitadel and Lago run as unmodified images, pinned: `ghcr.io/zitadel/zitadel:v4.20.0`, `ghcr.io/zitadel/zitadel-login:v4.20.0`, `getlago/api:v1.55.0`, `getlago/front:v1.55.0`, `getlago/lago-gotenberg:7.8.2`, Postgres image `getlago/postgres-partman:15.0-alpine` (Lago needs pg_partman), `redis:7-alpine`, `minio/minio:RELEASE.2025-09-07T16-13-09Z`, `stripe/stripe-cli:v1.55.6`.
- The backend is the only caller of Zitadel's and Lago's APIs. The frontend talks only to the backend (except the OIDC redirect to Zitadel's login and the Stripe-hosted checkout page).
- Access is decided only by `require_feature`. Plans change only in `backend/app/billing/plans.yaml`.
- Every product table carries `workspace_id`; jobs refuse queries without one.
- Missing data is never shown as `0`: loading → skeleton, failure → HTTP status + API message, absent → "Unavailable".
- Python package inside `backend/` is `app`; inside `jobs/` is `jobs`. Product-specific names come only from Copier answers.
- Stripe runs in test mode only. Live keys (`sk_live_`) are rejected at startup.
- Subscription states: `pending`, `active`, `past_due`, `canceled`. Access is granted in `active` and `past_due`.
- **Develop in a rendered product.** Edit files under `template/`, then `make dev` (root Makefile, Task 1) re-renders the template into `.dev/acme/` including uncommitted changes. Run every product command (`uv`, `npm`, `pytest`) inside `.dev/acme/<folder>`; never edit `.dev/` directly. After `uv lock` or `npm install` there, copy the lock file back into `template/<folder>/`.
- Only files that must vary per product end in `.jinja`. `pyproject.toml` and `package.json` use the fixed names `backend`, `jobs`, `scripts`, `frontend` so lock files stay identical across products.

## Review Focus

1. **Duplicate or out-of-order Lago webhooks** (retries, `subscription.started` arriving before `subscription.incomplete`): state must end correct and each event must apply at most once. → Task 6 test `test_out_of_order_events_end_active` and `test_duplicate_event_is_ignored`.
2. **A user who already has a workspace calls `POST /workspaces` again** (double-click, retry after network error): must return the existing workspace, not create a second Zitadel org or Lago customer. → Task 4 test `test_second_create_returns_existing_workspace`.
3. **Token for a workspace the backend doesn't know** (org created in Zitadel by hand, or row deleted): request must get `403`, never another workspace's data. → Task 3 test `test_unknown_org_is_forbidden`.
4. **Lago or Zitadel returns 5xx or times out mid-request**: client gets `503` naming the dependency; no half-written success. → Task 4 test `test_lago_down_returns_503_and_resumable`.
5. **Plan removed from `plans.yaml` while a workspace is still subscribed to it**: access must deny cleanly (402 "unknown plan"), not crash with `KeyError`. → Task 7 test `test_unknown_plan_denies`.

---

## File map

```
copier.yml                                  questions + tasks
CLAUDE.md                                   rules for agents working on the template
.github/workflows/template.yml              template self-test (generate → check → e2e)
tests/conftest.py                           generate a product into a temp dir once per session
tests/test_generate.py                      generated tree, answers applied, no secrets
template/
  .gitignore  .env.example.jinja  Makefile.jinja  docker-compose.yml.jinja  README.md.jinja
  CLAUDE.md.jinja  .claude/settings.json  .claude/hooks/guard.py  .claude/hooks/test_guard.py
  .github/workflows/{backend,frontend,jobs,e2e}.yml
  brand/brand.yaml.jinja  brand/logo.svg
  infra/README.md
  scripts/bootstrap.py  scripts/brand.py  scripts/doctor.py  scripts/postgres-init.sql
  backend/pyproject.toml.jinja  backend/Dockerfile  backend/alembic.ini  backend/migrations/…
  backend/app/{main,config,db,errors}.py
  backend/app/auth/{principal,tokens,deps}.py
  backend/app/integrations/{zitadel,lago}.py
  backend/app/workspaces/{models,service,routes}.py
  backend/app/billing/{plans.yaml.jinja,plans,models,checkout,webhooks,states,usage,routes,sync}.py
  backend/app/access/{rules,deps,routes}.py
  backend/app/demo/routes.py                premium_report sample feature
  backend/tests/…
  jobs/pyproject.toml  jobs/Dockerfile  jobs/schedules.yaml
  jobs/jobs/{runner,storage,db,scheduler}.py  jobs/jobs/handlers/{sample_fetch,billing_reconcile}.py
  jobs/tests/…
  frontend/package.json  frontend/vite.config.ts  frontend/index.html.jinja  frontend/eslint.config.js
  frontend/src/{main.tsx,App.tsx,routes.tsx,index.css,brand.css}
  frontend/src/api/{client.ts,schema.d.ts,queries.ts,errors.ts}
  frontend/src/auth/{userManager.ts,AuthGate.tsx}
  frontend/src/components/{ErrorState,Unavailable,PageSkeleton}.tsx  frontend/src/components/ui/…
  frontend/src/pages/{CreateWorkspace,Plans,Billing,PremiumReport,CheckoutReturn}.tsx (+ .test.tsx)
  e2e/package.json  e2e/playwright.config.ts  e2e/signup-to-premium.spec.ts
```

Each task below lists its exact files.

---

### Task 1: Archive the old code and lay down the template skeleton

**Files:**
- Delete: `packages/`, `data/`, `docker-compose.dev.yml`, `TODOS.md`, `DESIGN.md`, `obsidian/` (all preserved at tag `v1-diagnostic-archive`)
- Create: `copier.yml`, `CLAUDE.md`, `README.md` (replace), `Makefile`, `.gitignore`, `pyproject.toml` (template dev tools), `tests/conftest.py`, `tests/test_generate.py`, `template/.gitignore`, `template/README.md.jinja`, `template/infra/README.md`

**Interfaces:**
- Produces: Copier answers `product_name`, `product_slug`, `domain`, `brand_primary`, `brand_accent`, `brand_font`, `starter_plan_price_usd`, `starter_plan_interval`; pytest fixture `product_dir: pathlib.Path` (session-scoped, a generated product).

- [ ] **Step 1: Tag the current code** (do this before anything is deleted)

```bash
git switch main && git pull
git tag -a v1-diagnostic-archive -m "Copio Phase 1.0 diagnostic agent, archived before the boilerplate rewrite"
git switch -c feat/boilerplate-m1
```

Ask the human to run `git push origin v1-diagnostic-archive` (the repo is public; pushing is theirs to approve).

- [ ] **Step 2: Remove the old code**

```bash
git rm -r -q packages data docker-compose.dev.yml TODOS.md DESIGN.md obsidian
```

- [ ] **Step 3: Write the failing template test**

`pyproject.toml` (repo root, tooling only):

```toml
[project]
name = "copio-template"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["copier==9.19.1", "pytest>=8.3", "pyyaml>=6.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`tests/conftest.py`:

```python
import pathlib

import pytest
from copier import run_copy

ROOT = pathlib.Path(__file__).resolve().parents[1]

ANSWERS = {
    "product_name": "Acme Reports",
    "product_slug": "acme-reports",
    "domain": "acme-reports.localhost",
    "brand_primary": "#3355ff",
    "brand_accent": "#ff7a33",
    "brand_font": "Inter",
    "starter_plan_price_usd": 49,
    "starter_plan_interval": "month",
}


@pytest.fixture(scope="session")
def product_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    dest = tmp_path_factory.mktemp("product") / "acme-reports"
    run_copy(str(ROOT), str(dest), data=ANSWERS, defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)
    return dest
```

`tests/test_generate.py`:

```python
import pathlib
import re

SECRET_PATTERNS = [
    re.compile(r"sk_(live|test)_[0-9A-Za-z]{10,}"),
    re.compile(r"whsec_[0-9A-Za-z]{10,}"),
    re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def test_product_has_top_level_layout(product_dir: pathlib.Path) -> None:
    for name in ["backend", "frontend", "jobs", "infra", "brand", "README.md", ".gitignore"]:
        assert (product_dir / name).exists(), name


def test_answers_are_rendered(product_dir: pathlib.Path) -> None:
    readme = (product_dir / "README.md").read_text()
    assert "# Acme Reports" in readme
    assert "{{" not in readme


def test_env_is_ignored(product_dir: pathlib.Path) -> None:
    assert ".env" in (product_dir / ".gitignore").read_text().splitlines()


def test_no_secret_values_anywhere() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*"):
        if path.is_dir() or ".git" in path.parts or "node_modules" in path.parts:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(text) for p in SECRET_PATTERNS):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
```

- [ ] **Step 4: Run it to see it fail**

Run: `uv run pytest -q`
Expected: FAIL — `copier.yml` missing / `backend` does not exist.

- [ ] **Step 5: Create the template skeleton**

`copier.yml`:

```yaml
_subdirectory: template
_templates_suffix: .jinja
_answers_file: .copier-answers.yml

product_name:
  type: str
  help: Human name of the product
product_slug:
  type: str
  help: Lowercase slug, used for databases, buckets and Zitadel project
  default: "{{ product_name | lower | replace(' ', '-') }}"
  validator: "{% if not (product_slug | regex_search('^[a-z][a-z0-9-]{1,30}$')) %}lowercase letters, digits and dashes{% endif %}"
domain:
  type: str
  default: "{{ product_slug }}.localhost"
brand_primary:
  type: str
  default: "#2f6bff"
  validator: "{% if not (brand_primary | regex_search('^#[0-9a-fA-F]{6}$')) %}hex colour like #2f6bff{% endif %}"
brand_accent:
  type: str
  default: "#ff7a33"
  validator: "{% if not (brand_accent | regex_search('^#[0-9a-fA-F]{6}$')) %}hex colour like #ff7a33{% endif %}"
brand_font:
  type: str
  default: Inter
starter_plan_price_usd:
  type: int
  default: 29
starter_plan_interval:
  type: str
  choices: [month, year]
  default: month
```

`template/.gitignore`:

```
.env
node_modules/
dist/
__pycache__/
.venv/
.pytest_cache/
playwright-report/
test-results/
.bootstrap/
```

`template/README.md.jinja`:

```markdown
# {{ product_name }}

Generated from [prodij/copio](https://github.com/prodij/copio). Update with `copier update`.

    cp .env.example .env      # then fill in Stripe test keys
    make up && make bootstrap
    open http://{{ domain }}:5173
```

`template/infra/README.md`:

```markdown
# infra

Empty in milestone 1. Milestone 2 adds Terraform for a personal AWS account.
```

Root `Makefile`:

```make
dev:
	uv run copier copy . .dev/acme --vcs-ref HEAD --defaults --overwrite --trust \
	  -d product_name="Acme Reports" -d product_slug=acme-reports
```

Root `.gitignore`: `.dev/`, `.venv/`, `__pycache__/`, `node_modules/`.

Create empty placeholders so the layout test passes until later tasks fill them: `template/backend/.gitkeep`, `template/frontend/.gitkeep`, `template/jobs/.gitkeep`, `template/brand/.gitkeep`.

`CLAUDE.md` (repo root):

```markdown
# copio (template)

This repo is a Copier template. `template/` becomes a product; `tests/` generates one and tests it.

- Run `uv run pytest -q` before every commit; CI also runs the generated product's checks and e2e.
- Never commit secret values. `.env.example` lists names only.
- Never copy code from NG or Skylit repositories.
- Spec: docs/superpowers/specs/2026-10-30-boilerplate-milestone-1-design.md
```

Replace `README.md` with a short description: what Copio is (a SaaS boilerplate), `copier copy gh:prodij/copio my-product`, and a link to the spec and the archive tag.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: archive Phase 1.0 and start the Copier template"
```

---

> Note 2026-11-01 (Task 1 execution): the secret scan now iterates `git ls-files --cached --others --exclude-standard` instead of rglob, so ignored files (.venv, .dev) are skipped. Key-shaped fixture strings in this plan were shortened (`sk_test_x`, `sk_live_x`) so the plan itself passes the scan. Also: `data` was not tracked and was dropped from `git rm`; the Phase-1.0 root `.env.example` was removed; pytest config gained a `slow` marker with `-m 'not slow'` default; copier.yml gained the optional `logo_path` question (used by Task 11).


### Task 2: Backend foundation (settings, database, health, errors)

> **Note 2026-11-01 (Task 2):** `create_app(settings=None)` with lazy settings so importing `app.main` needs no env; `zitadel_service_token` defaults to `""`; ruff ignores E501 and imports are sorted (env.py); `alembic.ini` has `prepend_sys_path = .`; Dockerfile pins uv 0.10.2; added `tests/__init__.py` and an import-needs-no-env test (4 tests, not 3); dropped the unneeded `type: ignore[call-arg]` in `get_settings` (mypy strict flags it); test Postgres on host port 55432 via `TEST_DATABASE_URL`.

**Files:**
- Create: `template/backend/pyproject.toml`, `template/backend/Dockerfile`, `template/backend/alembic.ini`, `template/backend/migrations/env.py`, `template/backend/migrations/script.py.mako`, `template/backend/app/__init__.py`, `template/backend/app/main.py`, `template/backend/app/config.py`, `template/backend/app/db.py`, `template/backend/app/errors.py`, `template/backend/tests/conftest.py`, `template/backend/tests/test_health.py`, `template/backend/tests/test_config.py`
- Delete: `template/backend/.gitkeep`

**Interfaces:**
- Produces:
  - `app.config.Settings` (pydantic-settings) with fields `database_url: str`, `frontend_url: str`, `zitadel_issuer: str`, `zitadel_api_url: str`, `zitadel_project_id: str`, `zitadel_instance_org_id: str`, `zitadel_service_token: str`, `lago_api_url: str`, `lago_api_key: str`, `lago_webhook_issuer: str`, `lago_stripe_provider_code: str = "stripe"`, `stripe_secret_key: str`; `get_settings() -> Settings` (cached).
  - `app.db.Base` (DeclarativeBase), `app.db.get_session() -> Iterator[Session]` FastAPI dependency, `app.db.engine_for(url: str) -> Engine`.
  - `app.errors.DependencyUnavailable(dependency: str)` → handled as `503 {"detail": "<dependency> is unavailable"}`.
  - `app.main.create_app() -> FastAPI`; `GET /health -> {"status": "ok"}`.
  - Test fixtures `db_session: Session` (rolled back after each test), `client: TestClient` (overrides `get_session`), `settings: Settings`.

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/conftest.py`:

```python
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import Base, engine_for, get_session
from app.main import create_app

TEST_SETTINGS = Settings(
    database_url=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app_test"),
    frontend_url="http://app.test",
    zitadel_issuer="http://auth.test",
    zitadel_api_url="http://zitadel.test",
    zitadel_project_id="proj-1",
    zitadel_instance_org_id="org-instance",
    zitadel_service_token="test-token",
    lago_api_url="http://lago.test",
    lago_api_key="lago-key",
    lago_webhook_issuer="http://lago.test",
    stripe_secret_key="sk_test_x",
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return TEST_SETTINGS


@pytest.fixture(scope="session")
def connection(settings: Settings) -> Iterator[Connection]:
    engine = engine_for(settings.database_url)
    with engine.connect() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        conn.commit()
        yield conn


@pytest.fixture
def db_session(connection: Connection) -> Iterator[Session]:
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()


@pytest.fixture
def client(db_session: Session, settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
```

`template/backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.errors import DependencyUnavailable


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_dependency_unavailable_is_503(client: TestClient) -> None:
    app = client.app

    @app.get("/boom")  # type: ignore[attr-defined]
    def boom() -> None:
        raise DependencyUnavailable("Lago")

    response = client.get("/boom")
    assert response.status_code == 503
    assert response.json() == {"detail": "Lago is unavailable"}
```

`template/backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.config import Settings
from tests.conftest import TEST_SETTINGS


def test_live_stripe_key_is_rejected() -> None:
    data = TEST_SETTINGS.model_dump() | {"stripe_secret_key": "sk_live_abc"}
    with pytest.raises(ValidationError, match="test-mode"):
        Settings(**data)
```

- [ ] **Step 2: Run to verify failure**

Run (after `make dev`, in `.dev/acme/backend`, with a local Postgres: `docker run -d -p 5432:5432 -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app_test postgres:15-alpine`): `uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Implement**

`template/backend/pyproject.toml`:

```toml
[project]
name = "backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "sqlalchemy>=2.0.36",
  "psycopg[binary]>=3.2",
  "alembic>=1.14",
  "pydantic-settings>=2.6",
  "httpx>=0.28",
  "pyjwt[crypto]>=2.10",
  "pyyaml>=6.0",
]

[dependency-groups]
dev = ["pytest>=8.3", "respx>=0.21", "ruff>=0.8", "mypy>=1.13", "types-pyyaml"]

[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "SIM", "RUF"]
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
files = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`template/backend/app/config.py`:

```python
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    frontend_url: str
    zitadel_issuer: str
    zitadel_api_url: str
    zitadel_project_id: str
    zitadel_instance_org_id: str
    zitadel_service_token: str
    lago_api_url: str
    lago_api_key: str
    lago_webhook_issuer: str
    lago_stripe_provider_code: str = "stripe"
    stripe_secret_key: str

    @field_validator("stripe_secret_key")
    @classmethod
    def test_mode_only(cls, value: str) -> str:
        if not value.startswith("sk_test_"):
            raise ValueError("Stripe must run in test-mode (sk_test_...) in milestone 1")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

`template/backend/app/db.py`:

```python
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(engine_for(get_settings().database_url)) as session:
        yield session
```

`template/backend/app/errors.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DependencyUnavailable(Exception):
    def __init__(self, dependency: str) -> None:
        super().__init__(dependency)
        self.dependency = dependency


def install(app: FastAPI) -> None:
    @app.exception_handler(DependencyUnavailable)
    async def _unavailable(_: Request, exc: DependencyUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"{exc.dependency} is unavailable"})
```

`template/backend/app/main.py`:

```python
from fastapi import FastAPI

from app import errors


def create_app() -> FastAPI:
    app = FastAPI(title="api")
    errors.install(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

`template/backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
```

`template/backend/migrations/env.py`:

```python
from alembic import context

from app.config import get_settings
from app.db import Base, engine_for
import app.models_registry  # noqa: F401  (imports every model so autogenerate sees them)

target_metadata = Base.metadata

with engine_for(get_settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
```

Create `template/backend/app/models_registry.py` with only a docstring for now: `"""Imports every model module so Alembic sees all tables."""` (Tasks 4 and 5 add imports).

`template/backend/migrations/script.py.mako`: the standard Alembic template (copy from `alembic init` output, unmodified).

`template/backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Run tests**

Run: `make dev && cd .dev/acme/backend && uv lock && cp uv.lock ../../../template/backend/ && uv run pytest -q && uv run ruff check . && uv run mypy`
Expected: 3 passed; ruff and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add template/backend
git commit -m "feat(backend): settings, database, health and dependency errors"
```

---

### Task 3: Authentication from Zitadel tokens


> Note 2026-11-01: Zitadel v4.20.0 claim names verified (`urn:zitadel:iam:org:project:{id}:roles` shaped `{role: {orgId: domain}}`; audience scope `urn:zitadel:iam:org:project:id:{id}:aud`). Changes: `get_verifier` now depends on `get_settings` (cached per issuer/project) so importing needs no env (P8); conftest adds a session `tokens` fixture and `client` always overrides `get_verifier` (P7); `TokenFactory.verifier()` takes no argument (it owns the settings); added two `require_principal` 401/200 tests (9 tests in total for auth, not 7).
**Files:**
- Create: `template/backend/app/auth/__init__.py`, `principal.py`, `tokens.py`, `deps.py`; `template/backend/tests/auth_helpers.py`, `template/backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `Settings.zitadel_issuer`, `Settings.zitadel_project_id`.
- Produces:
  - `app.auth.principal.Principal(user_id: str, email: str | None, roles_by_org: dict[str, str])` (frozen dataclass; role is `"owner"` or `"member"`; owner wins when both).
  - `app.auth.tokens.TokenVerifier(issuer: str, project_id: str, jwks_client: jwt.PyJWKClient | None = None)` with `.verify(token: str) -> Principal`; raises `InvalidToken`.
  - `app.auth.deps.require_principal(...) -> Principal` (401 on missing/invalid token).
  - `app.auth.deps.get_verifier() -> TokenVerifier` (overridable in tests).
  - Test helper `tests.auth_helpers.TokenFactory` with `.make(user_id: str, orgs: dict[str, str], email: str = "u@example.com") -> str` and `.verifier(settings) -> TokenVerifier`.
- The "current workspace" dependency lives in Task 4 (`app.workspaces.routes.current_workspace`), because it needs the `workspaces` table.

Zitadel puts project roles in claim `urn:zitadel:iam:org:project:{projectId}:roles` shaped `{"owner": {"<orgId>": "<orgDomain>"}}`. The Zitadel app must use JWT access tokens and the project must have "assert roles on authentication" on (set by bootstrap, Task 11). The frontend requests scope `urn:zitadel:iam:org:project:id:{projectId}:aud` so the audience is the project ID.

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/auth_helpers.py`:

```python
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.tokens import TokenVerifier
from app.config import Settings


class _StaticJwks:
    def __init__(self, public_key: object) -> None:
        self._key = public_key

    def get_signing_key_from_jwt(self, _token: str) -> jwt.PyJWK:
        return jwt.PyJWK.from_dict(jwt.algorithms.RSAAlgorithm.to_jwk(self._key, as_dict=True) | {"alg": "RS256"})


class TokenFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def make(self, user_id: str, orgs: dict[str, str], email: str = "u@example.com", **overrides: object) -> str:
        roles: dict[str, dict[str, str]] = {}
        for org_id, role in orgs.items():
            roles.setdefault(role, {})[org_id] = f"{org_id}.test"
        claims = {
            "iss": self.settings.zitadel_issuer,
            "sub": user_id,
            "aud": [self.settings.zitadel_project_id],
            "exp": int(time.time()) + 300,
            "email": email,
            f"urn:zitadel:iam:org:project:{self.settings.zitadel_project_id}:roles": roles,
        } | overrides
        return jwt.encode(claims, self._private, algorithm="RS256")

    def verifier(self) -> TokenVerifier:
        return TokenVerifier(
            self.settings.zitadel_issuer,
            self.settings.zitadel_project_id,
            jwks_client=_StaticJwks(self._private.public_key()),  # type: ignore[arg-type]
        )
```

`template/backend/tests/test_auth.py`:

```python
import time

import pytest

from app.auth.tokens import InvalidToken
from app.config import Settings
from tests.auth_helpers import TokenFactory


@pytest.fixture
def factory(settings: Settings) -> TokenFactory:
    return TokenFactory(settings)


def test_roles_are_read_per_org(factory: TokenFactory) -> None:
    token = factory.make("user-1", {"org-a": "owner", "org-b": "member"})
    principal = factory.verifier().verify(token)
    assert principal.user_id == "user-1"
    assert principal.roles_by_org == {"org-a": "owner", "org-b": "member"}


def test_owner_wins_when_both_roles(factory: TokenFactory) -> None:
    claims_key = f"urn:zitadel:iam:org:project:{factory.settings.zitadel_project_id}:roles"
    token = factory.make(
        "user-1", {}, **{claims_key: {"member": {"org-a": "a"}, "owner": {"org-a": "a"}}}
    )
    assert factory.verifier().verify(token).roles_by_org == {"org-a": "owner"}


def test_no_roles_is_allowed(factory: TokenFactory) -> None:
    assert factory.verifier().verify(factory.make("user-1", {})).roles_by_org == {}


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "http://evil.test"},
        {"aud": ["other-project"]},
        {"exp": int(time.time()) - 10},
    ],
)
def test_bad_tokens_are_rejected(factory: TokenFactory, override: dict[str, object]) -> None:
    with pytest.raises(InvalidToken):
        factory.verifier().verify(factory.make("user-1", {}, **override))


def test_unsigned_garbage_is_rejected(factory: TokenFactory) -> None:
    with pytest.raises(InvalidToken):
        factory.verifier().verify("not-a-jwt")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_auth.py -q`
Expected: FAIL — `No module named 'app.auth'`.

- [ ] **Step 3: Implement**

`template/backend/app/auth/principal.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    roles_by_org: dict[str, str] = field(default_factory=dict)
```

`template/backend/app/auth/tokens.py`:

```python
from typing import Any

import jwt

from app.auth.principal import Principal

ROLE_RANK = {"member": 1, "owner": 2}


class InvalidToken(Exception):
    pass


class TokenVerifier:
    def __init__(self, issuer: str, project_id: str, jwks_client: jwt.PyJWKClient | None = None) -> None:
        self.issuer = issuer
        self.project_id = project_id
        self.jwks = jwks_client or jwt.PyJWKClient(f"{issuer}/oauth/v2/keys", cache_keys=True)

    def verify(self, token: str) -> Principal:
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.project_id,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidToken(str(exc)) from exc
        return Principal(
            user_id=str(claims["sub"]),
            email=claims.get("email"),
            roles_by_org=self._roles(claims),
        )

    def _roles(self, claims: dict[str, Any]) -> dict[str, str]:
        raw = claims.get(f"urn:zitadel:iam:org:project:{self.project_id}:roles") or {}
        result: dict[str, str] = {}
        for role, orgs in raw.items():
            if role not in ROLE_RANK or not isinstance(orgs, dict):
                continue
            for org_id in orgs:
                if ROLE_RANK[role] > ROLE_RANK.get(result.get(org_id, ""), 0):
                    result[org_id] = role
        return result
```

`template/backend/app/auth/deps.py`:

```python
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth.principal import Principal
from app.auth.tokens import InvalidToken, TokenVerifier
from app.config import get_settings


@lru_cache
def _default_verifier() -> TokenVerifier:
    s = get_settings()
    return TokenVerifier(s.zitadel_issuer, s.zitadel_project_id)


def get_verifier() -> TokenVerifier:
    return _default_verifier()


def require_principal(
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return verifier.verify(authorization.removeprefix("Bearer "))
    except InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_auth.py -q && uv run mypy`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add template/backend
git commit -m "feat(backend): verify Zitadel access tokens into a Principal"
```

---

### Task 4: Zitadel and Lago clients, workspaces, current workspace

> **Note 2026-11-01 (Task 4):** Upstream checked against Zitadel v4.20.0 protos/commands and lago-api v1.55.0 source; all endpoint paths, headers and body fields below are right. Changes, so a retry after a *lost response* resumes instead of duplicating or sticking (spec §5): `create_org(name, org_id)` sends `organizationId = workspace.id` and treats Zitadel's 409 as done; the org name is `"<name> (<first 8 of workspace id>)"` because Zitadel org names are unique per instance (two customers may both say "Acme"); `grant_project` on 409 looks the grant up via `POST /management/v1/projectgrants/_search` (`projectIdQuery` + `grantedOrgIdQuery`); `add_user_role` treats 409 as done. P32a: `zitadel_grant_id` is committed right after `grant_project`; the owner role grant is re-run on every resume (idempotent via 409) rather than given its own column. `get_zitadel`/`get_lago` take `Depends(get_settings)` (cached per settings values) instead of calling `get_settings()` directly. `ZitadelClient._post` takes `Mapping[str, object]` (mypy strict rejects `dict` invariance). P12: no local `tokens` fixture; conftest has an `auth` fixture (`auth(user_id, orgs=None, **claims) -> headers`, typed by `tests.auth_helpers.AuthHeaders`) instead of a per-file `auth()` helper. Added tests: role-grant failure resumes, lost Zitadel responses (409s) resume, `X-Workspace-Id` picks among several / foreign id → 403, `creating` workspace → 403 (16 tests in test_workspaces, not 11). Review fixes 2026-11-01: the first insert is `INSERT ... ON CONFLICT (owner_user_id) DO NOTHING` then re-select, so a simultaneous first POST resumes the winner's row instead of a 500; an empty grant search after a 409 (projection lag) is `DependencyUnavailable("Zitadel")`; `fake_zitadel(mock)` echoes the requested `organizationId` (= workspace id) like real Zitadel and no longer takes `org_id`, so later tests build owner tokens from the created workspace id, not `"org-new"` (18 tests). Heads-up for Tasks 5–8: Lago's `GET /api/v1/subscriptions/{external_id}` returns only an `active` subscription unless `?status=` is passed (pending ones give 404).

**Files:**
- Create: `template/backend/app/integrations/__init__.py`, `zitadel.py`, `lago.py`; `template/backend/app/workspaces/__init__.py`, `models.py`, `service.py`, `routes.py`; `template/backend/migrations/versions/0001_workspaces.py`; `template/backend/tests/test_workspaces.py`, `template/backend/tests/fakes.py`
- Modify: `template/backend/app/main.py` (include router), `template/backend/app/models_registry.py` (import `app.workspaces.models`)

**Interfaces:**
- Consumes: `Principal`, `require_principal`, `get_verifier`, `Settings`, `DependencyUnavailable`, `get_session`.
- Produces:
  - `app.integrations.zitadel.ZitadelClient(api_url, token, instance_org_id, project_id, http: httpx.Client | None = None)` with `create_org(name: str) -> str`, `grant_project(org_id: str) -> str` (returns project grant id), `add_user_role(user_id: str, org_id: str, grant_id: str, role: str) -> None`. All raise `DependencyUnavailable("Zitadel")` on network errors and 5xx.
  - `app.integrations.lago.LagoClient(api_url, api_key, http: httpx.Client | None = None)` with `create_customer(external_id: str, name: str, email: str | None, provider_code: str) -> str` (Lago id), `upsert_plan(body: dict) -> None`, `create_subscription(external_customer_id: str, plan_code: str, external_id: str) -> dict`, `checkout_url(external_customer_id: str) -> str`, `get_subscription(external_id: str) -> dict | None`, `record_event(transaction_id: str, external_subscription_id: str, code: str, properties: dict) -> None`, `webhook_public_key() -> str` (PEM). Raise `DependencyUnavailable("Lago")` on network errors and 5xx.
  - `get_zitadel() -> ZitadelClient`, `get_lago() -> LagoClient` FastAPI dependencies.
  - `app.workspaces.models.Workspace` (table `workspaces`: `id uuid pk`, `name`, `owner_user_id`, `zitadel_org_id unique null`, `zitadel_grant_id null`, `lago_customer_id null`, `status` in `creating|ready`, `created_at`).
  - `app.workspaces.service.create_workspace(session, principal, name, zitadel, lago, settings) -> Workspace` (resumable, idempotent per owner).
  - `app.workspaces.routes.current_workspace(...) -> CurrentWorkspace(workspace: Workspace, role: str)` dependency: picks the workspace whose `zitadel_org_id` is in `principal.roles_by_org`; `X-Workspace-Id` header chooses when there are several; 403 if none matches a known ready workspace.
  - Routes: `POST /workspaces {name}` → `201 {"id", "name", "status"}`; `GET /me` → `{"user_id", "email", "workspace": {...} | null}`.
  - `tests.fakes`: `fake_zitadel(respx_mock)` and `fake_lago(respx_mock)` helpers registering default happy responses.

Zitadel endpoints used: `POST /v2/organizations` body `{"name"}` → `{"organizationId"}`; `POST /management/v1/projects/{projectId}/grants` with header `x-zitadel-orgid: <instance org>` body `{"grantedOrgId", "roleKeys": ["owner","member"]}` → `{"grantId"}`; `POST /management/v1/users/{userId}/grants` with header `x-zitadel-orgid: <customer org>` body `{"projectId", "projectGrantId", "roleKeys": [role]}`.
Lago endpoints: `POST /api/v1/customers`, `POST /api/v1/plans`, `PUT /api/v1/plans/{code}`, `POST /api/v1/subscriptions`, `GET /api/v1/subscriptions/{external_id}`, `POST /api/v1/customers/{external_customer_id}/checkout_url` → `{"customer": {"checkout_url"}}`, `POST /api/v1/events`, `GET /api/v1/webhooks/json_public_key` → `{"webhook": {"public_key"}}` (base64-encoded PEM).

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/fakes.py`:

```python
import httpx
import respx

ZITADEL = "http://zitadel.test"
LAGO = "http://lago.test"


def fake_zitadel(mock: respx.MockRouter, org_id: str = "org-new") -> dict[str, respx.Route]:
    return {
        "org": mock.post(f"{ZITADEL}/v2/organizations").mock(
            return_value=httpx.Response(200, json={"organizationId": org_id})
        ),
        "grant": mock.post(f"{ZITADEL}/management/v1/projects/proj-1/grants").mock(
            return_value=httpx.Response(200, json={"grantId": "grant-1"})
        ),
        "user_grant": mock.post(url__regex=rf"{ZITADEL}/management/v1/users/.+/grants").mock(
            return_value=httpx.Response(200, json={"userGrantId": "ug-1"})
        ),
    }


def fake_lago(mock: respx.MockRouter) -> dict[str, respx.Route]:
    return {
        "customer": mock.post(f"{LAGO}/api/v1/customers").mock(
            return_value=httpx.Response(200, json={"customer": {"lago_id": "lago-cust-1"}})
        ),
    }
```

`template/backend/tests/test_workspaces.py`:

```python
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_verifier
from app.config import Settings
from app.workspaces.models import Workspace
from tests.auth_helpers import TokenFactory
from tests.fakes import LAGO, ZITADEL, fake_lago, fake_zitadel


@pytest.fixture
def tokens(settings: Settings, client: TestClient) -> TokenFactory:
    factory = TokenFactory(settings)
    client.app.dependency_overrides[get_verifier] = factory.verifier  # type: ignore[attr-defined]
    return factory


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@respx.mock
def test_create_workspace_happy_path(client: TestClient, tokens: TokenFactory, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    lago = fake_lago(respx.mock)
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth(tokens.make("user-1", {})))
    assert r.status_code == 201
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.status, ws.zitadel_org_id, ws.lago_customer_id) == ("ready", "org-new", "lago-cust-1")
    assert z["user_grant"].calls.last.request.headers["x-zitadel-orgid"] == "org-new"
    assert b'"owner"' in z["user_grant"].calls.last.request.content
    assert lago["customer"].calls.last.request.content.count(str(ws.id).encode()) == 1


@respx.mock
def test_second_create_returns_existing_workspace(client: TestClient, tokens: TokenFactory, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    headers = auth(tokens.make("user-1", {}))
    first = client.post("/workspaces", json={"name": "Acme"}, headers=headers).json()
    second = client.post("/workspaces", json={"name": "Acme again"}, headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert z["org"].call_count == 1
    assert len(db_session.scalars(select(Workspace)).all()) == 1


@respx.mock
def test_lago_down_returns_503_and_resumable(client: TestClient, tokens: TokenFactory, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    respx.post(f"{LAGO}/api/v1/customers").mock(return_value=httpx.Response(502))
    headers = auth(tokens.make("user-1", {}))
    r = client.post("/workspaces", json={"name": "Acme"}, headers=headers)
    assert r.status_code == 503
    assert r.json() == {"detail": "Lago is unavailable"}
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.status, ws.zitadel_org_id, ws.lago_customer_id) == ("creating", "org-new", None)

    respx.post(f"{LAGO}/api/v1/customers").mock(
        return_value=httpx.Response(200, json={"customer": {"lago_id": "lago-cust-1"}})
    )
    r = client.post("/workspaces", json={"name": "Acme"}, headers=headers)
    assert r.status_code == 201
    assert z["org"].call_count == 1
    assert db_session.scalars(select(Workspace)).one().status == "ready"


@respx.mock
def test_zitadel_timeout_returns_503(client: TestClient, tokens: TokenFactory) -> None:
    respx.post(f"{ZITADEL}/v2/organizations").mock(side_effect=httpx.ConnectTimeout("t"))
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth(tokens.make("user-1", {})))
    assert r.status_code == 503
    assert r.json() == {"detail": "Zitadel is unavailable"}


def test_me_without_workspace(client: TestClient, tokens: TokenFactory) -> None:
    r = client.get("/me", headers=auth(tokens.make("user-1", {}, email="a@b.c")))
    assert r.json() == {"user_id": "user-1", "email": "a@b.c", "workspace": None}


@respx.mock
def test_me_with_workspace(client: TestClient, tokens: TokenFactory) -> None:
    fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    ws = client.post("/workspaces", json={"name": "Acme"}, headers=auth(tokens.make("user-1", {}))).json()
    r = client.get("/me", headers=auth(tokens.make("user-1", {"org-new": "owner"})))
    assert r.json()["workspace"] == {"id": ws["id"], "name": "Acme", "role": "owner"}


def test_unknown_org_is_forbidden(client: TestClient, tokens: TokenFactory) -> None:
    r = client.get("/me/workspace", headers=auth(tokens.make("user-1", {"org-unknown": "owner"})))
    assert r.status_code == 403


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.post("/workspaces", json={"name": "x"}).status_code == 401


@pytest.mark.parametrize("name", ["", " ", "x" * 81])
def test_bad_names_are_422(client: TestClient, tokens: TokenFactory, name: str) -> None:
    r = client.post("/workspaces", json={"name": name}, headers=auth(tokens.make("user-1", {})))
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_workspaces.py -q`
Expected: FAIL — `No module named 'app.workspaces'`.

- [ ] **Step 3: Implement the clients**

`template/backend/app/integrations/zitadel.py`:

```python
import httpx

from app.errors import DependencyUnavailable


class ZitadelClient:
    def __init__(self, api_url: str, token: str, instance_org_id: str, project_id: str,
                 http: httpx.Client | None = None) -> None:
        self.instance_org_id = instance_org_id
        self.project_id = project_id
        self.http = http or httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {token}"}, timeout=10.0
        )

    def _post(self, path: str, body: dict[str, object], org_id: str | None = None) -> dict[str, object]:
        headers = {"x-zitadel-orgid": org_id} if org_id else {}
        try:
            response = self.http.post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable("Zitadel") from exc
        if response.status_code >= 500:
            raise DependencyUnavailable("Zitadel")
        response.raise_for_status()
        result: dict[str, object] = response.json()
        return result

    def create_org(self, name: str) -> str:
        return str(self._post("/v2/organizations", {"name": name})["organizationId"])

    def grant_project(self, org_id: str) -> str:
        body = {"grantedOrgId": org_id, "roleKeys": ["owner", "member"]}
        path = f"/management/v1/projects/{self.project_id}/grants"
        return str(self._post(path, body, org_id=self.instance_org_id)["grantId"])

    def add_user_role(self, user_id: str, org_id: str, grant_id: str, role: str) -> None:
        body = {"projectId": self.project_id, "projectGrantId": grant_id, "roleKeys": [role]}
        self._post(f"/management/v1/users/{user_id}/grants", body, org_id=org_id)
```

`template/backend/app/integrations/lago.py`:

```python
import base64
from typing import Any

import httpx

from app.errors import DependencyUnavailable


class LagoClient:
    def __init__(self, api_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15.0
        )

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = self.http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable("Lago") from exc
        if response.status_code >= 500:
            raise DependencyUnavailable("Lago")
        return response

    def create_customer(self, external_id: str, name: str, email: str | None, provider_code: str) -> str:
        body = {"customer": {
            "external_id": external_id,
            "name": name,
            "email": email,
            "billing_configuration": {
                "payment_provider": "stripe",
                "payment_provider_code": provider_code,
                "sync_with_provider": True,
                "provider_payment_methods": ["card"],
            },
        }}
        response = self._call("POST", "/api/v1/customers", body)
        response.raise_for_status()
        return str(response.json()["customer"]["lago_id"])

    def upsert_plan(self, body: dict[str, Any]) -> None:
        code = body["plan"]["code"]
        response = self._call("PUT", f"/api/v1/plans/{code}", body)
        if response.status_code == 404:
            response = self._call("POST", "/api/v1/plans", body)
        response.raise_for_status()

    def create_subscription(self, external_customer_id: str, plan_code: str, external_id: str) -> dict[str, Any]:
        body = {"subscription": {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            "external_id": external_id,
            "activation_rules": [{"type": "payment", "timeout_hours": 48}],
        }}
        response = self._call("POST", "/api/v1/subscriptions", body)
        response.raise_for_status()
        result: dict[str, Any] = response.json()["subscription"]
        return result

    def checkout_url(self, external_customer_id: str) -> str:
        response = self._call("POST", f"/api/v1/customers/{external_customer_id}/checkout_url")
        response.raise_for_status()
        return str(response.json()["customer"]["checkout_url"])

    def get_subscription(self, external_id: str) -> dict[str, Any] | None:
        response = self._call("GET", f"/api/v1/subscriptions/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        result: dict[str, Any] = response.json()["subscription"]
        return result

    def record_event(self, transaction_id: str, external_subscription_id: str, code: str,
                     properties: dict[str, Any]) -> None:
        body = {"event": {"transaction_id": transaction_id, "external_subscription_id": external_subscription_id,
                          "code": code, "properties": properties}}
        self._call("POST", "/api/v1/events", body).raise_for_status()

    def webhook_public_key(self) -> str:
        response = self._call("GET", "/api/v1/webhooks/json_public_key")
        response.raise_for_status()
        return base64.b64decode(response.json()["webhook"]["public_key"]).decode()
```

Add to `template/backend/app/integrations/__init__.py`:

```python
from functools import lru_cache

from app.config import get_settings
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient


@lru_cache
def _zitadel() -> ZitadelClient:
    s = get_settings()
    return ZitadelClient(s.zitadel_api_url, s.zitadel_service_token, s.zitadel_instance_org_id, s.zitadel_project_id)


@lru_cache
def _lago() -> LagoClient:
    s = get_settings()
    return LagoClient(s.lago_api_url, s.lago_api_key)


def get_zitadel() -> ZitadelClient:
    return _zitadel()


def get_lago() -> LagoClient:
    return _lago()
```

In `tests/conftest.py`'s `client` fixture, also override the clients so tests hit the respx fakes:

```python
from app.integrations import get_lago, get_zitadel
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
# inside client(), before TestClient(app):
    app.dependency_overrides[get_zitadel] = lambda: ZitadelClient(
        settings.zitadel_api_url, "t", settings.zitadel_instance_org_id, settings.zitadel_project_id
    )
    app.dependency_overrides[get_lago] = lambda: LagoClient(settings.lago_api_url, "k")
```

- [ ] **Step 4: Implement workspaces**

`template/backend/app/workspaces/models.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    owner_user_id: Mapped[str] = mapped_column(String(64), unique=True)
    zitadel_org_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    zitadel_grant_id: Mapped[str | None] = mapped_column(String(64))
    lago_customer_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="creating")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

`owner_user_id` is unique: milestone 1 allows one owned workspace per user, which is what makes `POST /workspaces` idempotent.

`template/backend/app/workspaces/service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.config import Settings
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
from app.workspaces.models import Workspace


def create_workspace(session: Session, principal: Principal, name: str, zitadel: ZitadelClient,
                     lago: LagoClient, settings: Settings) -> tuple[Workspace, bool]:
    """Returns (workspace, created_now). Each step is committed, so a retry resumes."""
    ws = session.scalars(select(Workspace).where(Workspace.owner_user_id == principal.user_id)).one_or_none()
    if ws is not None and ws.status == "ready":
        return ws, False
    if ws is None:
        ws = Workspace(name=name, owner_user_id=principal.user_id)
        session.add(ws)
        session.commit()
    if ws.zitadel_org_id is None:
        ws.zitadel_org_id = zitadel.create_org(ws.name)
        session.commit()
    if ws.zitadel_grant_id is None:
        ws.zitadel_grant_id = zitadel.grant_project(ws.zitadel_org_id)
        zitadel.add_user_role(principal.user_id, ws.zitadel_org_id, ws.zitadel_grant_id, "owner")
        session.commit()
    if ws.lago_customer_id is None:
        ws.lago_customer_id = lago.create_customer(str(ws.id), ws.name, principal.email,
                                                   settings.lago_stripe_provider_code)
        session.commit()
    ws.status = "ready"
    session.commit()
    return ws, True
```

`template/backend/app/workspaces/routes.py`:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_principal
from app.auth.principal import Principal
from app.config import Settings, get_settings
from app.db import get_session
from app.integrations import get_lago, get_zitadel
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
from app.workspaces.models import Workspace
from app.workspaces.service import create_workspace

router = APIRouter()


class CreateWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class WorkspaceOut(BaseModel):
    id: str
    name: str
    status: str


class MeWorkspace(BaseModel):
    id: str
    name: str
    role: str


class MeOut(BaseModel):
    user_id: str
    email: str | None
    workspace: MeWorkspace | None


@dataclass(frozen=True)
class CurrentWorkspace:
    workspace: Workspace
    role: str


def _find(session: Session, principal: Principal, wanted: str | None) -> CurrentWorkspace | None:
    if not principal.roles_by_org:
        return None
    rows = session.scalars(
        select(Workspace).where(Workspace.zitadel_org_id.in_(principal.roles_by_org), Workspace.status == "ready")
    ).all()
    if wanted:
        rows = [w for w in rows if str(w.id) == wanted]
    if not rows:
        return None
    ws = sorted(rows, key=lambda w: w.created_at)[0]
    return CurrentWorkspace(ws, principal.roles_by_org[ws.zitadel_org_id or ""])


def current_workspace(
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> CurrentWorkspace:
    found = _find(session, principal, x_workspace_id)
    if found is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No workspace for this user")
    return found


@router.post("/workspaces", status_code=201, response_model=WorkspaceOut)
def post_workspace(
    body: CreateWorkspace,
    response: Response,
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
    zitadel: Annotated[ZitadelClient, Depends(get_zitadel)],
    lago: Annotated[LagoClient, Depends(get_lago)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceOut:
    ws, created = create_workspace(session, principal, body.name, zitadel, lago, settings)
    if not created:
        response.status_code = 200
    return WorkspaceOut(id=str(ws.id), name=ws.name, status=ws.status)


@router.get("/me", response_model=MeOut)
def get_me(
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
) -> MeOut:
    found = _find(session, principal, None)
    ws = MeWorkspace(id=str(found.workspace.id), name=found.workspace.name, role=found.role) if found else None
    return MeOut(user_id=principal.user_id, email=principal.email, workspace=ws)


@router.get("/me/workspace", response_model=MeWorkspace)
def get_my_workspace(current: Annotated[CurrentWorkspace, Depends(current_workspace)]) -> MeWorkspace:
    return MeWorkspace(id=str(current.workspace.id), name=current.workspace.name, role=current.role)
```

In `app/main.py` add `from app.workspaces.routes import router as workspaces_router` and `app.include_router(workspaces_router)` inside `create_app`. In `app/models_registry.py` add `import app.workspaces.models  # noqa: F401`.

`template/backend/migrations/versions/0001_workspaces.py`:

```python
"""workspaces"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("owner_user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("zitadel_org_id", sa.String(64), unique=True),
        sa.Column("zitadel_grant_id", sa.String(64)),
        sa.Column("lago_customer_id", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspaces")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy`
Expected: all pass (test_workspaces: 11 passed).

- [ ] **Step 6: Commit**

```bash
git add template/backend
git commit -m "feat(backend): Zitadel and Lago clients, resumable workspace creation"
```

---

### Task 5: Plans, plan sync and checkout

> **Note 2026-11-01 (Task 5, upstream finding, coordinator ruling: option A):** Checked against lago-api v1.55.0. The plan's checkout order fails for every new workspace, so checkout now works as described below.
> - **What breaks:** a subscription created with `activation_rules: [{type: payment}]` needs a default payment method already (`ActivationRules::Payment::ValidateService` → 422 `customer: ["no_default_payment_method"]`). Lago's `checkout_url` is a Stripe Checkout session in **setup mode**: it saves a card and charges nothing. Lago sends **no webhook** when the card is saved (`setup_intent.succeeded` goes to Lago only).
> - **How `POST /billing/checkout` works now:**
>   - It always records the choice first: one `subscriptions` row per workspace, `state=pending`, `lago_subscription_id` null until a Lago subscription exists. The column is now nullable.
>   - No default card (`GET /api/v1/customers/{id}/payment_methods`, `is_default`) → `{"checkout_url": <setup URL>}`.
>   - Card present → create the payment-gated subscription once (external id `{workspace_id}:{plan_code}`) → `{"checkout_url": null}`. Lago's 422 `subscription_incomplete` on a repeat create means it already exists, so it counts as done.
>   - An existing Lago subscription → `null` with no Lago call. A `canceled` row starts over.
>   - Access still comes only from the webhooks (Task 6).
> - **Errors:**
>   - Lago 4xx on checkout → `app.errors.DependencyRejected` → 502 `"Lago rejected the request: <code> <details>"`, not a bare 500.
>   - A Lago customer whose Stripe customer is not synced yet (`billing_configuration.provider_customer_id` empty; Lago creates it in a job) → 503 `"Stripe customer is unavailable"`. Otherwise the session would have no Stripe customer and the card would never reach Lago.
> - **Code changes:**
>   - `LagoClient` gains `has_default_payment_method(external_customer_id)`. `checkout_url` first GETs the customer. `create_subscription` returns `None`.
>   - `start_checkout(...) -> str | None`. `CheckoutOut.checkout_url: str | None`.
>   - `sync.py` calls `get_lago(get_settings())`.
>   - `load_plans` also rejects missing fields and non-integer amounts.
> - **Fixtures (P12):** conftest has `owner_workspace` (creates user-1's workspace, returns its id) and `owner_headers` (owner token for that id). `tests.fakes.fake_lago_billing(mock, card=, synced=)` fakes the checkout endpoints. Tasks 6, 7 and 13 use these and do not import from `test_checkout`.
> - **Tests:** 21 in test_checkout + test_plans, not 8.
> - **Follow-ons:**
>   - **Task 10:** `CheckoutReturn` calls `POST /billing/checkout` once more, with the plan chosen before the redirect, before it polls `/me/access`. `Plans.tsx` goes straight to `/billing/return` when `checkout_url` is null. A `pending` row can now exist before any payment, so "no plan" in the `/` redirect should mean no row, or `pending` with no Lago subscription.
>   - **Task 8:** `billing_reconcile` also finishes a workspace whose row is `pending` with `lago_subscription_id IS NULL` (checkout started, owner never came back) once the Lago customer has a default payment method: create the gated subscription with the same external id and store it.
>   - **Tasks 6 and 8:** look subscriptions up by `lago_subscription_id`. Rows where it is null have no Lago subscription.

**Files:**
- Create: `template/backend/app/billing/__init__.py`, `plans.yaml.jinja`, `plans.py`, `models.py`, `checkout.py`, `routes.py`, `sync.py`; `template/backend/migrations/versions/0002_billing.py`; `template/backend/tests/test_plans.py`, `template/backend/tests/test_checkout.py`
- Modify: `app/main.py` (include billing router), `app/models_registry.py` (import `app.billing.models`)

**Interfaces:**
- Consumes: `CurrentWorkspace`, `current_workspace`, `LagoClient`, `get_lago`.
- Produces:
  - `app.billing.plans.Plan(code: str, name: str, amount_cents: int, currency: str, interval: str, features: dict[str, bool | int])`; `load_plans(path: Path = PLANS_PATH) -> dict[str, Plan]` (validates: unique codes, interval in `month|year`, amount ≥ 0, feature values bool or int ≥ 0); `get_plans() -> dict[str, Plan]` (cached dependency); `Plan.to_lago() -> dict`.
  - `app.billing.models.Subscription` (table `subscriptions`: `workspace_id uuid pk fk`, `plan_code`, `state`, `lago_subscription_id` (= our external id), `current_period_end null`, `updated_at`) and `WebhookEvent` (table `webhook_events`: `id` text pk (`X-Lago-Unique-Key`), `type`, `received_at`, `payload jsonb`, `processed_at null`).
  - `app.billing.checkout.start_checkout(session, ws: Workspace, plan: Plan, lago: LagoClient) -> str` (returns checkout URL; creates `Subscription(state="pending")` once; repeated calls reuse it and only regenerate the URL).
  - Route `POST /billing/checkout {plan_code}` (owner only) → `{"checkout_url"}`; `GET /billing/plans` → list of plans (public fields only).
  - CLI `python -m app.billing.sync` pushes all plans to Lago.

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/test_plans.py`:

```python
import pathlib

import pytest

from app.billing.plans import PlanFileError, load_plans


def write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    p = tmp_path / "plans.yaml"
    p.write_text(text)
    return p


def test_shipped_plans_load() -> None:
    plans = load_plans()
    assert "starter" in plans
    assert plans["starter"].features["premium_report"] is True


def test_to_lago_shape() -> None:
    body = load_plans()["starter"].to_lago()
    assert body["plan"]["code"] == "starter"
    assert body["plan"]["pay_in_advance"] is True
    assert body["plan"]["interval"] in {"monthly", "yearly"}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: week, features: {}}]", "interval"),
        ("plans: [{code: a, name: A, amount_cents: -1, currency: USD, interval: month, features: {}}]", "amount"),
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: month, features: {}},"
         " {code: a, name: B, amount_cents: 1, currency: USD, interval: month, features: {}}]", "duplicate"),
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: month, features: {x: maybe}}]", "feature"),
    ],
)
def test_bad_plan_files_are_rejected(tmp_path: pathlib.Path, text: str, message: str) -> None:
    with pytest.raises(PlanFileError, match=message):
        load_plans(write(tmp_path, text))
```

`template/backend/tests/test_checkout.py`:

```python
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_verifier
from app.billing.models import Subscription
from app.config import Settings
from tests.auth_helpers import TokenFactory
from tests.fakes import LAGO, fake_lago, fake_zitadel


@pytest.fixture
def owner_headers(client: TestClient, settings: Settings) -> dict[str, str]:
    factory = TokenFactory(settings)
    client.app.dependency_overrides[get_verifier] = factory.verifier  # type: ignore[attr-defined]
    with respx.mock:
        fake_zitadel(respx.mock)
        fake_lago(respx.mock)
        client.post("/workspaces", json={"name": "Acme"},
                    headers={"Authorization": f"Bearer {factory.make('user-1', {})}"})
    client.app.state.factory = factory  # type: ignore[attr-defined]
    return {"Authorization": f"Bearer {factory.make('user-1', {'org-new': 'owner'})}"}


def lago_checkout(mock: respx.MockRouter) -> dict[str, respx.Route]:
    return {
        "sub": mock.post(f"{LAGO}/api/v1/subscriptions").mock(
            return_value=httpx.Response(200, json={"subscription": {"external_id": "x", "status": "incomplete"}})
        ),
        "url": mock.post(url__regex=rf"{LAGO}/api/v1/customers/.+/checkout_url").mock(
            return_value=httpx.Response(200, json={"customer": {"checkout_url": "https://checkout.stripe.test/s"}})
        ),
    }


@respx.mock
def test_checkout_returns_url_and_creates_pending(client: TestClient, owner_headers: dict[str, str],
                                                  db_session: Session) -> None:
    routes = lago_checkout(respx.mock)
    r = client.post("/billing/checkout", json={"plan_code": "starter"}, headers=owner_headers)
    assert r.status_code == 200
    assert r.json() == {"checkout_url": "https://checkout.stripe.test/s"}
    sub = db_session.scalars(select(Subscription)).one()
    assert (sub.plan_code, sub.state) == ("starter", "pending")
    assert b'"activation_rules"' in routes["sub"].calls.last.request.content


@respx.mock
def test_repeat_checkout_reuses_subscription(client: TestClient, owner_headers: dict[str, str]) -> None:
    routes = lago_checkout(respx.mock)
    client.post("/billing/checkout", json={"plan_code": "starter"}, headers=owner_headers)
    client.post("/billing/checkout", json={"plan_code": "starter"}, headers=owner_headers)
    assert routes["sub"].call_count == 1
    assert routes["url"].call_count == 2


def test_unknown_plan_is_422(client: TestClient, owner_headers: dict[str, str]) -> None:
    r = client.post("/billing/checkout", json={"plan_code": "gold"}, headers=owner_headers)
    assert r.status_code == 422


def test_member_cannot_checkout(client: TestClient, owner_headers: dict[str, str]) -> None:
    factory: TokenFactory = client.app.state.factory  # type: ignore[attr-defined]
    member = {"Authorization": f"Bearer {factory.make('user-2', {'org-new': 'member'})}"}
    assert client.post("/billing/checkout", json={"plan_code": "starter"}, headers=member).status_code == 403


def test_list_plans(client: TestClient) -> None:
    plans = client.get("/billing/plans").json()
    assert plans[0]["code"] == "starter"
    assert set(plans[0]) == {"code", "name", "amount_cents", "currency", "interval", "features"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_plans.py tests/test_checkout.py -q`
Expected: FAIL — `No module named 'app.billing'`.

- [ ] **Step 3: Implement**

`template/backend/app/billing/plans.yaml.jinja`:

```yaml
# Plans are code: edit here, then `make sync-plans`.
plans:
  - code: starter
    name: Starter
    amount_cents: {{ starter_plan_price_usd * 100 }}
    currency: USD
    interval: {{ starter_plan_interval }}
    features:
      premium_report: true
      seats: 5
```

`template/backend/app/billing/plans.py`:

```python
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PLANS_PATH = Path(__file__).with_name("plans.yaml")
LAGO_INTERVAL = {"month": "monthly", "year": "yearly"}


class PlanFileError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    amount_cents: int
    currency: str
    interval: str
    features: dict[str, bool | int] = field(default_factory=dict)

    def to_lago(self) -> dict[str, Any]:
        return {"plan": {
            "code": self.code,
            "name": self.name,
            "amount_cents": self.amount_cents,
            "amount_currency": self.currency,
            "interval": LAGO_INTERVAL[self.interval],
            "pay_in_advance": True,
            "charges": [],
        }}

    def public(self) -> dict[str, Any]:
        return {"code": self.code, "name": self.name, "amount_cents": self.amount_cents,
                "currency": self.currency, "interval": self.interval, "features": dict(self.features)}


def load_plans(path: Path = PLANS_PATH) -> dict[str, Plan]:
    raw = yaml.safe_load(path.read_text()) or {}
    plans: dict[str, Plan] = {}
    for item in raw.get("plans", []):
        code = str(item["code"])
        if code in plans:
            raise PlanFileError(f"duplicate plan code {code!r}")
        if item["interval"] not in LAGO_INTERVAL:
            raise PlanFileError(f"plan {code!r}: interval must be month or year")
        if int(item["amount_cents"]) < 0:
            raise PlanFileError(f"plan {code!r}: amount_cents must be >= 0")
        features = item.get("features") or {}
        for name, value in features.items():
            if not (isinstance(value, bool) or (isinstance(value, int) and value >= 0)):
                raise PlanFileError(f"plan {code!r}: feature {name!r} must be true/false or a whole number")
        plans[code] = Plan(code, str(item["name"]), int(item["amount_cents"]), str(item["currency"]),
                           str(item["interval"]), dict(features))
    return plans


@lru_cache
def get_plans() -> dict[str, Plan]:
    return load_plans()
```

`template/backend/app/billing/models.py`:

```python
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Subscription(Base):
    __tablename__ = "subscriptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))
    lago_subscription_id: Mapped[str] = mapped_column(String(64), unique=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

`template/backend/app/billing/checkout.py`:

```python
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.billing.plans import Plan
from app.integrations.lago import LagoClient
from app.workspaces.models import Workspace


def start_checkout(session: Session, ws: Workspace, plan: Plan, lago: LagoClient) -> str:
    sub = session.get(Subscription, ws.id)
    if sub is None or sub.state == "canceled":
        external_id = f"{ws.id}:{plan.code}"
        lago.create_subscription(str(ws.id), plan.code, external_id)
        if sub is None:
            sub = Subscription(workspace_id=ws.id, plan_code=plan.code, state="pending",
                               lago_subscription_id=external_id)
            session.add(sub)
        else:
            sub.plan_code, sub.state, sub.lago_subscription_id = plan.code, "pending", external_id
        session.commit()
    return lago.checkout_url(str(ws.id))
```

`template/backend/app/billing/routes.py`:

```python
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.billing.checkout import start_checkout
from app.billing.plans import Plan, get_plans
from app.db import get_session
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter(prefix="/billing")


class CheckoutIn(BaseModel):
    plan_code: str


class CheckoutOut(BaseModel):
    checkout_url: str


@router.get("/plans")
def list_plans(plans: Annotated[dict[str, Plan], Depends(get_plans)]) -> list[dict[str, Any]]:
    return [p.public() for p in plans.values()]


@router.post("/checkout", response_model=CheckoutOut)
def checkout(
    body: CheckoutIn,
    current: Annotated[CurrentWorkspace, Depends(current_workspace)],
    session: Annotated[Session, Depends(get_session)],
    lago: Annotated[LagoClient, Depends(get_lago)],
    plans: Annotated[dict[str, Plan], Depends(get_plans)],
) -> CheckoutOut:
    if current.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can change the plan")
    plan = plans.get(body.plan_code)
    if plan is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown plan {body.plan_code!r}")
    return CheckoutOut(checkout_url=start_checkout(session, current.workspace, plan, lago))
```

`template/backend/app/billing/sync.py`:

```python
from app.billing.plans import load_plans
from app.integrations import get_lago


def main() -> None:
    lago = get_lago()
    for plan in load_plans().values():
        lago.upsert_plan(plan.to_lago())
        print(f"synced plan {plan.code}")


if __name__ == "__main__":
    main()
```

`template/backend/migrations/versions/0002_billing.py`:

```python
"""billing"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("lago_subscription_id", sa.String(64), nullable=False, unique=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("subscriptions")
```

Include the router in `create_app` and import `app.billing.models` in `models_registry.py`. `load_plans()` reads the rendered `plans.yaml`, which exists only in the rendered product, which is why all backend tests run in `.dev/acme/backend`.

- [ ] **Step 4: Run tests**

Run: `make dev && cd .dev/acme/backend && uv run pytest tests/test_plans.py tests/test_checkout.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add template/backend
git commit -m "feat(billing): plans as code, plan sync, payment-gated checkout"
```

---

### Task 6: Lago webhooks and subscription states

> **Note 2026-11-01 (Task 6, checked against lago-api v1.55.0; rulings P28, P31c, P16, P32b):**
> - **Signature (plan was right):** `X-Lago-Signature` is an RS256 JWT `{data: <body JSON>, iss: LAGO_API_URL}`; key from `GET /api/v1/webhooks/json_public_key` (base64 PEM). `X-Lago-Unique-Key` is Lago's webhook id, the same on every retry. Lago can also sign with HMAC (`X-Lago-Signature-Algorithm: hmac`); we accept only `jwt` (Lago's default), so the bootstrap must create the endpoint with `signature_algo: jwt`.
> - **Invoice matching (plan was wrong):** invoice webhooks do not carry `invoice.subscriptions[]` (the serializer includes only `customer` and `fees`). Subscriptions come from `invoice.fees[].external_subscription_id`.
> - **`invoice.payment_failure` (plan was wrong):** its `object_type` is `payment_provider_invoice_payment_error`, and it names only the customer (`external_customer_id`, which is our workspace id). We match the workspace's subscription by that id.
> - **Gated activation:** Lago sends `subscription.incomplete` on create and `subscription.started` once the first invoice is paid. A failed or timed-out first payment sends `subscription.canceled`, which maps to `canceled` (Task 5 parked ruling), so the owner can restart checkout.
> - **Unknown types (P28):** a type in Lago's list (`config/webhook_event_types.yml`, 75 types, held as `LAGO_WEBHOOK_TYPES`) that we don't act on → 200, stored, logged. A type not in the list → 400, not stored.
> - **Also:** `current_period_end` comes from `subscription.current_billing_period_ending_at` on `subscription.*` webhooks and never moves backwards (P16). The route is `async` only to read the raw body; verify and the DB work run in a threadpool (P32b). `get_webhook_verifier` takes settings and the Lago client through `Depends`. Tests use fixture payloads in `backend/tests/fixtures/lago/` (P31c).

**Files:**
- Create: `template/backend/app/billing/states.py`, `template/backend/app/billing/webhooks.py`; `template/backend/tests/test_states.py`, `template/backend/tests/test_webhooks.py`
- Modify: `template/backend/app/billing/routes.py` (add webhook route)

**Interfaces:**
- Consumes: `Subscription`, `WebhookEvent`, `LagoClient.webhook_public_key`, `Settings.lago_webhook_issuer`.
- Produces:
  - `app.billing.states.next_state(current: str, webhook_type: str, payment_status: str | None = None) -> str` — pure function, the only place state transitions are defined:

    | webhook_type | from | to |
    |---|---|---|
    | `subscription.incomplete` | `pending` | `pending` (any other: unchanged) |
    | `subscription.started` | any except `canceled` | `active` |
    | `subscription.canceled`, `subscription.terminated` | any | `canceled` |
    | `invoice.payment_failure` | `active` | `past_due` |
    | `invoice.payment_status_updated` + `failed` | `active` | `past_due` |
    | `invoice.payment_status_updated` + `succeeded` | `past_due` | `active` |
    | anything else | — | unchanged |

  - `app.billing.webhooks.WebhookVerifier(public_key_pem: str, issuer: str).verify(raw_body: bytes, signature: str) -> dict` (JWT RS256, `iss` = issuer, `data` JSON equals body JSON; raises `BadSignature`).
  - `app.billing.webhooks.handle_event(session, event_id: str, payload: dict) -> bool` (False if already processed).
  - `get_webhook_verifier() -> WebhookVerifier` (fetches and caches the public key from Lago on first use).
  - Route `POST /billing/webhooks/lago` → `200 {"status": "ok" | "duplicate"}`; `400` on bad signature, missing `X-Lago-Unique-Key`, or invalid JSON.

Subscriptions in webhooks are matched by `subscription.external_id` (our `lago_subscription_id`); invoices by each `invoice.subscriptions[].external_id`.

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/test_states.py`:

```python
import pytest

from app.billing.states import next_state


@pytest.mark.parametrize(
    ("current", "webhook", "payment", "expected"),
    [
        ("pending", "subscription.incomplete", None, "pending"),
        ("active", "subscription.incomplete", None, "active"),
        ("pending", "subscription.started", None, "active"),
        ("past_due", "subscription.started", None, "active"),
        ("canceled", "subscription.started", None, "canceled"),
        ("active", "subscription.canceled", None, "canceled"),
        ("pending", "subscription.terminated", None, "canceled"),
        ("active", "invoice.payment_failure", None, "past_due"),
        ("pending", "invoice.payment_failure", None, "pending"),
        ("active", "invoice.payment_status_updated", "failed", "past_due"),
        ("past_due", "invoice.payment_status_updated", "succeeded", "active"),
        ("active", "invoice.payment_status_updated", "pending", "active"),
        ("active", "customer.created", None, "active"),
    ],
)
def test_transitions(current: str, webhook: str, payment: str | None, expected: str) -> None:
    assert next_state(current, webhook, payment) == expected
```

`template/backend/tests/test_webhooks.py`:

```python
import json
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.billing.models import Subscription, WebhookEvent
from app.billing.webhooks import WebhookVerifier, get_webhook_verifier
from app.workspaces.models import Workspace

ISSUER = "http://lago.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


@pytest.fixture
def sub(db_session: Session, client: TestClient) -> Subscription:
    client.app.dependency_overrides[get_webhook_verifier] = lambda: WebhookVerifier(PEM, ISSUER)  # type: ignore[attr-defined]
    ws = Workspace(name="Acme", owner_user_id=f"u-{uuid.uuid4()}", status="ready")
    db_session.add(ws)
    db_session.flush()
    s = Subscription(workspace_id=ws.id, plan_code="starter", state="pending", lago_subscription_id=f"{ws.id}:starter")
    db_session.add(s)
    db_session.flush()
    return s


def send(client: TestClient, payload: dict[str, object], key: str | None = None, sign_with: object = KEY,
         issuer: str = ISSUER) -> int:
    body = json.dumps(payload)
    token = jwt.encode({"data": body, "iss": issuer}, sign_with, algorithm="RS256")
    headers = {"X-Lago-Signature": token, "X-Lago-Signature-Algorithm": "jwt",
               "X-Lago-Unique-Key": key or str(uuid.uuid4()), "Content-Type": "application/json"}
    return client.post("/billing/webhooks/lago", content=body, headers=headers).status_code


def sub_event(kind: str, s: Subscription) -> dict[str, object]:
    return {"webhook_type": kind, "object_type": "subscription",
            "subscription": {"external_id": s.lago_subscription_id, "status": "active"}}


def invoice_event(kind: str, s: Subscription, payment_status: str) -> dict[str, object]:
    return {"webhook_type": kind, "object_type": "invoice",
            "invoice": {"payment_status": payment_status, "subscriptions": [{"external_id": s.lago_subscription_id}]}}


def test_started_activates(client: TestClient, sub: Subscription, db_session: Session) -> None:
    assert send(client, sub_event("subscription.started", sub)) == 200
    db_session.refresh(sub)
    assert sub.state == "active"


def test_duplicate_event_is_ignored(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.started", sub), key="evt-1")
    send(client, invoice_event("invoice.payment_status_updated", sub, "failed"), key="evt-2")
    assert send(client, sub_event("subscription.started", sub), key="evt-2") == 200
    db_session.refresh(sub)
    assert sub.state == "past_due"
    assert db_session.get(WebhookEvent, "evt-2") is not None


def test_out_of_order_events_end_active(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.started", sub))
    send(client, sub_event("subscription.incomplete", sub))
    db_session.refresh(sub)
    assert sub.state == "active"


def test_bad_signature_is_400(client: TestClient, sub: Subscription, db_session: Session) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert send(client, sub_event("subscription.started", sub), sign_with=other) == 400
    assert send(client, sub_event("subscription.started", sub), issuer="http://evil") == 400
    db_session.refresh(sub)
    assert sub.state == "pending"


def test_body_must_match_signed_data(client: TestClient, sub: Subscription) -> None:
    signed = json.dumps(sub_event("subscription.canceled", sub))
    token = jwt.encode({"data": signed, "iss": ISSUER}, KEY, algorithm="RS256")
    body = json.dumps(sub_event("subscription.started", sub))
    r = client.post("/billing/webhooks/lago", content=body,
                    headers={"X-Lago-Signature": token, "X-Lago-Unique-Key": "k", "Content-Type": "application/json"})
    assert r.status_code == 400


def test_missing_unique_key_is_400(client: TestClient, sub: Subscription) -> None:
    body = json.dumps(sub_event("subscription.started", sub))
    token = jwt.encode({"data": body, "iss": ISSUER}, KEY, algorithm="RS256")
    r = client.post("/billing/webhooks/lago", content=body, headers={"X-Lago-Signature": token})
    assert r.status_code == 400


def test_unknown_subscription_is_acknowledged(client: TestClient, sub: Subscription) -> None:
    payload = {"webhook_type": "subscription.started", "object_type": "subscription",
               "subscription": {"external_id": "someone-else"}}
    assert send(client, payload) == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_states.py tests/test_webhooks.py -q`
Expected: FAIL — `No module named 'app.billing.states'`.

- [ ] **Step 3: Implement**

`template/backend/app/billing/states.py`:

```python
GRANTING = frozenset({"active", "past_due"})


def next_state(current: str, webhook_type: str, payment_status: str | None = None) -> str:
    if webhook_type in {"subscription.canceled", "subscription.terminated"}:
        return "canceled"
    if webhook_type == "subscription.started":
        return current if current == "canceled" else "active"
    if webhook_type == "invoice.payment_failure":
        return "past_due" if current == "active" else current
    if webhook_type == "invoice.payment_status_updated":
        if payment_status == "failed" and current == "active":
            return "past_due"
        if payment_status == "succeeded" and current == "past_due":
            return "active"
    return current
```

`template/backend/app/billing/webhooks.py`:

```python
import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.billing.models import Subscription, WebhookEvent
from app.billing.states import next_state
from app.config import get_settings
from app.integrations import get_lago


class BadSignature(Exception):
    pass


class WebhookVerifier:
    def __init__(self, public_key_pem: str, issuer: str) -> None:
        self.key = public_key_pem
        self.issuer = issuer

    def verify(self, raw_body: bytes, signature: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(signature, self.key, algorithms=["RS256"], issuer=self.issuer,
                                options={"require": ["iss"], "verify_aud": False})
            body = json.loads(raw_body)
            if json.loads(claims["data"]) != body:
                raise BadSignature("body does not match signed data")
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise BadSignature(str(exc)) from exc
        result: dict[str, Any] = body
        return result


@lru_cache
def _verifier() -> WebhookVerifier:
    return WebhookVerifier(get_lago().webhook_public_key(), get_settings().lago_webhook_issuer)


def get_webhook_verifier() -> WebhookVerifier:
    return _verifier()


def _subscription_ids(payload: dict[str, Any]) -> list[str]:
    if payload.get("object_type") == "subscription":
        return [str(payload.get("subscription", {}).get("external_id", ""))]
    if payload.get("object_type") == "invoice":
        return [str(s.get("external_id", "")) for s in payload.get("invoice", {}).get("subscriptions", [])]
    return []


def handle_event(session: Session, event_id: str, payload: dict[str, Any]) -> bool:
    webhook_type = str(payload.get("webhook_type", ""))
    inserted = session.execute(
        insert(WebhookEvent).values(id=event_id, type=webhook_type, payload=payload)
        .on_conflict_do_nothing(index_elements=["id"]).returning(WebhookEvent.id)
    ).scalar_one_or_none()
    if inserted is None:
        return False
    payment_status = payload.get("invoice", {}).get("payment_status")
    for external_id in _subscription_ids(payload):
        sub = session.scalars(
            select(Subscription).where(Subscription.lago_subscription_id == external_id).with_for_update()
        ).one_or_none()
        if sub is not None:
            sub.state = next_state(sub.state, webhook_type, payment_status)
    event = session.get(WebhookEvent, event_id)
    if event is not None:
        event.processed_at = datetime.now(UTC)
    session.commit()
    return True
```

Add to `template/backend/app/billing/routes.py`:

```python
from fastapi import Header, Request

from app.billing.webhooks import BadSignature, WebhookVerifier, get_webhook_verifier, handle_event


@router.post("/webhooks/lago")
async def lago_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    verifier: Annotated[WebhookVerifier, Depends(get_webhook_verifier)],
    x_lago_signature: Annotated[str | None, Header()] = None,
    x_lago_unique_key: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if not x_lago_signature or not x_lago_unique_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing Lago signature or unique key")
    try:
        payload = verifier.verify(await request.body(), x_lago_signature)
    except BadSignature as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad signature") from exc
    processed = handle_event(session, x_lago_unique_key, payload)
    return {"status": "ok" if processed else "duplicate"}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_states.py tests/test_webhooks.py -q && uv run mypy`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add template/backend
git commit -m "feat(billing): verified, idempotent Lago webhooks drive subscription state"
```

---

### Task 7: Access rules, `/me/access`, usage, and the sample premium feature

**Files:**
- Create: `template/backend/app/access/__init__.py`, `rules.py`, `deps.py`, `routes.py`; `template/backend/app/billing/usage.py`; `template/backend/app/demo/__init__.py`, `routes.py`; `template/backend/tests/test_access.py`
- Modify: `app/main.py` (include access and demo routers)

**Interfaces:**
- Consumes: `CurrentWorkspace`, `current_workspace`, `Subscription`, `get_plans`, `GRANTING`, `LagoClient.record_event`.
- Produces:
  - `app.access.rules.decide(state: str | None, plan_code: str | None, plans: dict[str, Plan], feature: str) -> Decision(allowed: bool, reason: str)`.
  - `app.access.deps.require_feature(feature: str) -> Callable` — FastAPI dependency factory; raises `402 {"detail": reason}` when denied; returns `CurrentWorkspace`.
  - `GET /me/access` → `{"plan_code": str | None, "state": str | None, "features": dict}`.
  - `app.billing.usage.record_usage(lago, session, workspace_id, metric: str, value: int) -> None` (no-op when the workspace has no subscription).
  - `GET /demo/premium-report` → `{"title": "Premium report", "generated_for": "<workspace name>"}` behind `require_feature("premium_report")`; records usage metric `reports_generated`.

- [ ] **Step 1: Write the failing tests**

`template/backend/tests/test_access.py`:

```python
import itertools

import pytest

from app.access.rules import decide
from app.billing.plans import Plan

PLANS = {
    "starter": Plan("starter", "Starter", 100, "USD", "month", {"premium_report": True, "seats": 5}),
    "free": Plan("free", "Free", 0, "USD", "month", {"premium_report": False}),
}
STATES = [None, "pending", "active", "past_due", "canceled"]
PLAN_CODES = [None, "starter", "free"]
FEATURES = ["premium_report", "seats", "not_a_feature"]


def expected(state: str | None, plan: str | None, feature: str) -> bool:
    if state not in {"active", "past_due"} or plan is None:
        return False
    return bool(PLANS[plan].features.get(feature, False))


@pytest.mark.parametrize(("state", "plan", "feature"), list(itertools.product(STATES, PLAN_CODES, FEATURES)))
def test_every_combination(state: str | None, plan: str | None, feature: str) -> None:
    assert decide(state, plan, PLANS, feature).allowed is expected(state, plan, feature)


def test_unknown_plan_denies() -> None:
    decision = decide("active", "gold", PLANS, "premium_report")
    assert decision.allowed is False
    assert decision.reason == "unknown plan 'gold'"


def test_reasons_are_human() -> None:
    assert decide(None, None, PLANS, "premium_report").reason == "no subscription"
    assert decide("pending", "starter", PLANS, "premium_report").reason == "subscription is pending"
    assert decide("active", "free", PLANS, "premium_report").reason == "plan 'free' does not include premium_report"
```

Add endpoint tests to the same file:

```python
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.workspaces.models import Workspace
from tests.test_checkout import owner_headers  # noqa: F401  (fixture)


def _subscribe(db_session: Session, state: str) -> None:
    ws = db_session.query(Workspace).one()
    db_session.add(Subscription(workspace_id=ws.id, plan_code="starter", state=state,
                                lago_subscription_id=f"{ws.id}:starter"))
    db_session.flush()


@respx.mock
def test_premium_report_needs_active_plan(client: TestClient, owner_headers: dict[str, str],
                                          db_session: Session) -> None:
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert r.status_code == 402
    assert r.json() == {"detail": "no subscription"}
    _subscribe(db_session, "active")
    respx.post("http://lago.test/api/v1/events").respond(200, json={})
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert r.status_code == 200
    assert r.json()["generated_for"] == "Acme"


def test_me_access(client: TestClient, owner_headers: dict[str, str], db_session: Session) -> None:
    assert client.get("/me/access", headers=owner_headers).json() == {
        "plan_code": None, "state": None, "features": {}}
    _subscribe(db_session, "past_due")
    body = client.get("/me/access", headers=owner_headers).json()
    assert body == {"plan_code": "starter", "state": "past_due", "features": {"premium_report": True, "seats": 5}}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_access.py -q`
Expected: FAIL — `No module named 'app.access'`.

- [ ] **Step 3: Implement**

`template/backend/app/access/rules.py`:

```python
from dataclasses import dataclass

from app.billing.plans import Plan
from app.billing.states import GRANTING


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def decide(state: str | None, plan_code: str | None, plans: dict[str, Plan], feature: str) -> Decision:
    if state is None or plan_code is None:
        return Decision(False, "no subscription")
    if state not in GRANTING:
        return Decision(False, f"subscription is {state}")
    plan = plans.get(plan_code)
    if plan is None:
        return Decision(False, f"unknown plan {plan_code!r}")
    if not plan.features.get(feature):
        return Decision(False, f"plan {plan_code!r} does not include {feature}")
    return Decision(True, "ok")
```

`template/backend/app/access/deps.py`:

```python
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access.rules import decide
from app.billing.models import Subscription
from app.billing.plans import Plan, get_plans
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace


def require_feature(feature: str) -> Callable[..., CurrentWorkspace]:
    def dependency(
        current: Annotated[CurrentWorkspace, Depends(current_workspace)],
        session: Annotated[Session, Depends(get_session)],
        plans: Annotated[dict[str, Plan], Depends(get_plans)],
    ) -> CurrentWorkspace:
        sub = session.get(Subscription, current.workspace.id)
        decision = decide(sub.state if sub else None, sub.plan_code if sub else None, plans, feature)
        if not decision.allowed:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, decision.reason)
        return current

    return dependency
```

`template/backend/app/access/routes.py`:

```python
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.billing.plans import Plan, get_plans
from app.billing.states import GRANTING
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter()


@router.get("/me/access")
def my_access(
    current: Annotated[CurrentWorkspace, Depends(current_workspace)],
    session: Annotated[Session, Depends(get_session)],
    plans: Annotated[dict[str, Plan], Depends(get_plans)],
) -> dict[str, Any]:
    sub = session.get(Subscription, current.workspace.id)
    if sub is None:
        return {"plan_code": None, "state": None, "features": {}}
    plan = plans.get(sub.plan_code)
    features = dict(plan.features) if plan and sub.state in GRANTING else {}
    return {"plan_code": sub.plan_code, "state": sub.state, "features": features}
```

`template/backend/app/billing/usage.py`:

```python
import uuid

from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.integrations.lago import LagoClient


def record_usage(lago: LagoClient, session: Session, workspace_id: uuid.UUID, metric: str, value: int) -> None:
    sub = session.get(Subscription, workspace_id)
    if sub is None:
        return
    lago.record_event(str(uuid.uuid4()), sub.lago_subscription_id, metric, {"value": value})
```

`template/backend/app/demo/routes.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.access.deps import require_feature
from app.billing.usage import record_usage
from app.db import get_session
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.routes import CurrentWorkspace

router = APIRouter(prefix="/demo")


@router.get("/premium-report")
def premium_report(
    current: Annotated[CurrentWorkspace, Depends(require_feature("premium_report"))],
    session: Annotated[Session, Depends(get_session)],
    lago: Annotated[LagoClient, Depends(get_lago)],
) -> dict[str, str]:
    record_usage(lago, session, current.workspace.id, "reports_generated", 1)
    return {"title": "Premium report", "generated_for": current.workspace.name}
```

Include `access` and `demo` routers in `create_app`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy`
Expected: all pass (`test_access.py`: 50 passed).

- [ ] **Step 5: Export the API contract and commit**

Add `template/backend/app/export_openapi.py`:

```python
import json
from pathlib import Path

from app.main import create_app

Path("openapi.json").write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
```

Run: `uv run python -m app.export_openapi` (writes `template/backend/openapi.json`).

```bash
git add template/backend
git commit -m "feat(access): require_feature, /me/access, usage and sample premium feature"
```

---

### Task 8: Jobs — raw-first storage, workspace-scoped database, scheduler, reconcile

**Files:**
- Create: `template/jobs/pyproject.toml`, `template/jobs/Dockerfile`, `template/jobs/schedules.yaml`, `template/jobs/jobs/__init__.py`, `runner.py`, `storage.py`, `db.py`, `scheduler.py`, `template/jobs/jobs/handlers/__init__.py`, `sample_fetch.py`, `billing_reconcile.py`; `template/jobs/tests/test_storage.py`, `test_db.py`, `test_scheduler.py`, `test_handlers.py`
- Delete: `template/jobs/.gitkeep`

**Interfaces:**
- Consumes: backend tables `workspaces`, `subscriptions` (read/write through SQL, not by importing backend code); Lago `GET /api/v1/subscriptions/{external_id}`.
- Produces:
  - Handler contract: `handler(event: dict, context: object | None) -> dict` in each `jobs/handlers/<name>.py`.
  - `jobs.storage.RawStore(bucket: str, client)` with `.put_raw(source: str, workspace_id: str, run_id: str, ext: str, body: bytes, when: date) -> str` (returns key `raw/<source>/<workspace_id>/<yyyy>/<mm>/<dd>/<run_id>.<ext>`) and `.get(key) -> bytes`.
  - `jobs.db.ScopedDb(engine)` with `.execute(sql: str, params: dict) -> list[dict]`; raises `MissingWorkspaceScope` unless `params` has `workspace_id` and the SQL references `:workspace_id`. `.unscoped_workspaces() -> list[dict]` is the single allowed cross-workspace read (id list for fan-out).
  - `jobs.scheduler.load_schedules(path) -> list[Schedule(name, cron)]`, `due(schedules, now: datetime, last_run: dict[str, datetime]) -> list[str]`, `main()` loop (checks every 30 s).
  - `jobs.runner.run(name: str, event: dict) -> dict` (imports `jobs.handlers.<name>.handler`).
  - Lago state mapping for reconcile: Lago `active` → ours unchanged if `past_due`, else `active`; `incomplete`/`pending` → `pending`; `canceled`/`terminated` → `canceled`; 404 → unchanged.

- [ ] **Step 1: Write the failing tests**

`template/jobs/tests/test_storage.py`:

```python
from datetime import date

import boto3
from moto import mock_aws

from jobs.storage import RawStore


@mock_aws
def test_raw_key_layout_and_roundtrip() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="raw")
    store = RawStore("raw", client)
    key = store.put_raw("feed", "ws-1", "run-9", "json", b'{"a":1}', date(2026, 10, 31))
    assert key == "raw/feed/ws-1/2026/10/31/run-9.json"
    assert store.get(key) == b'{"a":1}'
```

`template/jobs/tests/test_db.py`:

```python
import pytest
from sqlalchemy import create_engine

from jobs.db import MissingWorkspaceScope, ScopedDb


@pytest.fixture
def db() -> ScopedDb:
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table rows (workspace_id text, v int)")
        c.exec_driver_sql("insert into rows values ('a', 1), ('b', 2)")
        c.exec_driver_sql("create table workspaces (id text, status text)")
        c.exec_driver_sql("insert into workspaces values ('a', 'ready'), ('b', 'creating')")
    return ScopedDb(engine)


def test_scoped_query_only_sees_its_workspace(db: ScopedDb) -> None:
    rows = db.execute("select v from rows where workspace_id = :workspace_id", {"workspace_id": "a"})
    assert rows == [{"v": 1}]


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ("select v from rows", {}),
        ("select v from rows", {"workspace_id": "a"}),
        ("select v from rows where workspace_id = :workspace_id", {}),
    ],
)
def test_unscoped_queries_are_refused(db: ScopedDb, sql: str, params: dict[str, str]) -> None:
    with pytest.raises(MissingWorkspaceScope):
        db.execute(sql, params)


def test_fan_out_lists_ready_workspaces(db: ScopedDb) -> None:
    assert db.unscoped_workspaces() == [{"id": "a"}]
```

`template/jobs/tests/test_scheduler.py`:

```python
from datetime import UTC, datetime

from jobs.scheduler import Schedule, due


def test_due_runs_once_per_slot() -> None:
    s = [Schedule("billing_reconcile", "*/15 * * * *")]
    now = datetime(2026, 10, 31, 12, 15, 5, tzinfo=UTC)
    assert due(s, now, {}) == ["billing_reconcile"]
    assert due(s, now, {"billing_reconcile": datetime(2026, 10, 31, 12, 15, 1, tzinfo=UTC)}) == []
    assert due(s, now, {"billing_reconcile": datetime(2026, 10, 31, 12, 0, 1, tzinfo=UTC)}) == ["billing_reconcile"]
```

`template/jobs/tests/test_handlers.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import create_engine, text

from jobs.handlers import billing_reconcile


@pytest.fixture
def engine():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table workspaces (id text, status text)")
        c.exec_driver_sql("create table subscriptions (workspace_id text, plan_code text, state text,"
                          " lago_subscription_id text, updated_at text)")
        for ws, state in [("a", "pending"), ("b", "past_due"), ("c", "active"), ("d", "active")]:
            c.execute(text("insert into workspaces values (:w, 'ready')"), {"w": ws})
            c.execute(text("insert into subscriptions values (:w, 'starter', :s, :x, '')"),
                      {"w": ws, "s": state, "x": f"{ws}:starter"})
    return engine


@respx.mock
def test_reconcile_repairs_states(engine) -> None:  # type: ignore[no-untyped-def]
    lago = "http://lago.test/api/v1/subscriptions"
    respx.get(f"{lago}/a:starter").respond(200, json={"subscription": {"status": "active"}})
    respx.get(f"{lago}/b:starter").respond(200, json={"subscription": {"status": "active"}})
    respx.get(f"{lago}/c:starter").respond(200, json={"subscription": {"status": "terminated"}})
    respx.get(f"{lago}/d:starter").respond(500)
    result = billing_reconcile.reconcile(engine, httpx.Client(base_url="http://lago.test"))
    with engine.connect() as c:
        states = dict(c.execute(text("select workspace_id, state from subscriptions")).all())
    assert states == {"a": "active", "b": "past_due", "c": "canceled", "d": "active"}
    assert result == {"checked": 4, "changed": 2, "errors": 1}
```

- [ ] **Step 2: Run to verify failure**

Run: `make dev && cd .dev/acme/jobs && uv run pytest -q`
Expected: FAIL — `No module named 'jobs.storage'`.

- [ ] **Step 3: Implement**

`template/jobs/pyproject.toml`:

```toml
[project]
name = "jobs"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = ["boto3>=1.35", "sqlalchemy>=2.0.36", "psycopg[binary]>=3.2", "httpx>=0.28",
                "croniter>=5.0", "pyyaml>=6.0"]

[dependency-groups]
dev = ["pytest>=8.3", "respx>=0.21", "moto[s3]>=5.0", "ruff>=0.8", "mypy>=1.13", "types-pyyaml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`template/jobs/jobs/storage.py`:

```python
from datetime import date
from typing import Any


class RawStore:
    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    def put_raw(self, source: str, workspace_id: str, run_id: str, ext: str, body: bytes, when: date) -> str:
        key = f"raw/{source}/{workspace_id}/{when:%Y/%m/%d}/{run_id}.{ext}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body)
        return key

    def get(self, key: str) -> bytes:
        body: bytes = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        return body
```

`template/jobs/jobs/db.py`:

```python
from typing import Any

from sqlalchemy import Engine, text


class MissingWorkspaceScope(Exception):
    pass


class ScopedDb:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not params.get("workspace_id") or ":workspace_id" not in sql:
            raise MissingWorkspaceScope(sql)
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return [dict(row._mapping) for row in result] if result.returns_rows else []

    def unscoped_workspaces(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text("select id from workspaces where status = 'ready' order by id"))
            return [dict(r._mapping) for r in rows]
```

`template/jobs/jobs/scheduler.py`:

```python
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from croniter import croniter

from jobs.runner import run

SCHEDULES = Path(__file__).resolve().parents[1] / "schedules.yaml"


@dataclass(frozen=True)
class Schedule:
    name: str
    cron: str


def load_schedules(path: Path = SCHEDULES) -> list[Schedule]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [Schedule(str(s["job"]), str(s["cron"])) for s in raw.get("schedules", [])]


def due(schedules: list[Schedule], now: datetime, last_run: dict[str, datetime]) -> list[str]:
    names = []
    for s in schedules:
        slot = croniter(s.cron, now).get_prev(datetime)
        last = last_run.get(s.name)
        if last is None or last < slot:
            names.append(s.name)
    return names


def main() -> None:
    schedules = load_schedules()
    last_run: dict[str, datetime] = {}
    while True:
        now = datetime.now(UTC)
        for name in due(schedules, now, last_run):
            last_run[name] = now
            print(name, run(name, {}), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
```

`template/jobs/jobs/runner.py`:

```python
import importlib
from typing import Any


def run(name: str, event: dict[str, Any]) -> dict[str, Any]:
    module = importlib.import_module(f"jobs.handlers.{name}")
    result: dict[str, Any] = module.handler(event, None)
    return result
```

`template/jobs/schedules.yaml`:

```yaml
# job: module name under jobs/handlers; cron in UTC. Milestone 2 turns these into EventBridge schedules.
schedules:
  - job: billing_reconcile
    cron: "*/15 * * * *"
  - job: sample_fetch
    cron: "0 * * * *"
```

`template/jobs/jobs/handlers/billing_reconcile.py`:

```python
import os
from typing import Any

import httpx
from sqlalchemy import Engine, create_engine, text

LAGO_TO_OURS = {"incomplete": "pending", "pending": "pending", "canceled": "canceled", "terminated": "canceled"}


def _target(current: str, lago_status: str) -> str:
    if lago_status == "active":
        return current if current == "past_due" else "active"
    return LAGO_TO_OURS.get(lago_status, current)


def reconcile(engine: Engine, lago: httpx.Client) -> dict[str, int]:
    checked = changed = errors = 0
    with engine.connect() as conn:
        subs = conn.execute(text("select workspace_id, state, lago_subscription_id from subscriptions")).all()
    for workspace_id, state, external_id in subs:
        checked += 1
        try:
            response = lago.get(f"/api/v1/subscriptions/{external_id}")
        except httpx.HTTPError:
            errors += 1
            continue
        if response.status_code == 404:
            continue
        if response.status_code >= 400:
            errors += 1
            continue
        target = _target(state, response.json()["subscription"]["status"])
        if target != state:
            with engine.begin() as conn:
                conn.execute(text("update subscriptions set state = :s where workspace_id = :w"),
                             {"s": target, "w": workspace_id})
            changed += 1
    return {"checked": checked, "changed": changed, "errors": errors}


def handler(event: dict[str, Any], context: object | None) -> dict[str, int]:
    engine = create_engine(os.environ["DATABASE_URL"])
    lago = httpx.Client(base_url=os.environ["LAGO_API_URL"],
                        headers={"Authorization": f"Bearer {os.environ['LAGO_API_KEY']}"}, timeout=15.0)
    return reconcile(engine, lago)
```

`template/jobs/jobs/handlers/sample_fetch.py`:

```python
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import httpx
from sqlalchemy import create_engine

from jobs.db import ScopedDb
from jobs.storage import RawStore

FEED = "https://api.github.com/zen"


def handler(event: dict[str, Any], context: object | None) -> dict[str, Any]:
    """Fetch a public value once per workspace: raw to storage first, then one processed row."""
    db = ScopedDb(create_engine(os.environ["DATABASE_URL"]))
    s3 = boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL"))
    store = RawStore(os.environ["RAW_BUCKET"], s3)
    run_id = uuid.uuid4().hex
    body = httpx.get(FEED, timeout=10.0).content
    stored = 0
    for ws in db.unscoped_workspaces():
        key = store.put_raw("zen", str(ws["id"]), run_id, "txt", body, datetime.now(UTC).date())
        db.execute(
            "insert into sample_rows (workspace_id, raw_key, value) values (:workspace_id, :raw_key, :value)",
            {"workspace_id": ws["id"], "raw_key": key, "value": json.dumps(store.get(key).decode())},
        )
        stored += 1
    return {"run_id": run_id, "workspaces": stored}
```

Add the `sample_rows` table to the backend (so Alembic owns every table): `template/backend/migrations/versions/0003_sample_rows.py` with columns `id bigserial pk`, `workspace_id uuid fk workspaces.id not null`, `raw_key text not null`, `value text not null`, `created_at timestamptz default now()`.

`template/jobs/Dockerfile`:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv
WORKDIR /jobs
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
CMD ["uv", "run", "--no-dev", "python", "-m", "jobs.scheduler"]
```

- [ ] **Step 4: Run tests**

Run: `make dev && cd .dev/acme/jobs && uv lock && cp uv.lock ../../../template/jobs/ && uv run pytest -q && uv run ruff check .`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add template/jobs template/backend/migrations
git commit -m "feat(jobs): raw-first storage, workspace-scoped db, scheduler and billing reconcile"
```

---

### Task 9: Frontend foundation — Vite, Tailwind, shadcn, typed client, states

**Files:**
- Create: `template/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html.jinja`, `eslint.config.js`, `components.json`, `src/main.tsx`, `src/index.css`, `src/brand.css` (generated placeholder, overwritten by `make brand`), `src/api/client.ts`, `src/api/errors.ts`, `src/api/queries.ts`, `src/api/schema.d.ts` (generated), `src/components/ErrorState.tsx`, `src/components/Unavailable.tsx`, `src/components/PageSkeleton.tsx`, `src/test/setup.ts`, `src/test/utils.tsx`, `src/components/ErrorState.test.tsx`, `src/api/errors.test.ts`
- Delete: `template/frontend/.gitkeep`

**Interfaces:**
- Consumes: `template/backend/openapi.json`.
- Produces:
  - `api` (openapi-fetch client) from `src/api/client.ts`; bearer token injected per request by middleware `setTokenProvider(fn: () => Promise<string | null>)`.
  - `ApiError(status: number, detail: string)` from `src/api/errors.ts`; `toApiError(response: Response, body: unknown): ApiError`.
  - TanStack Query options in `src/api/queries.ts`: `meQuery`, `accessQuery`, `plansQuery`, `premiumReportQuery`; mutations `createWorkspace(name)`, `startCheckout(planCode)`.
  - Components `ErrorState({ error }: { error: ApiError })`, `Unavailable()`, `PageSkeleton()`.
  - Test helpers `renderWithQuery(ui)`, `mockFetch(routes: Record<string, { status: number; body: unknown }>)`.

- [ ] **Step 1: Scaffold**

```bash
make dev   # scaffold once in the rendered product, then copy the files back into template/frontend/
cd .dev/acme/frontend
npm create vite@latest . -- --template react-ts --no-interactive
npm install @tanstack/react-query openapi-fetch oidc-client-ts react-router @base-ui/react
npm install -D tailwindcss @tailwindcss/vite openapi-typescript vitest @testing-library/react @testing-library/jest-dom jsdom
npx shadcn@latest init   # choose the Base UI base and the base-vega style when prompted
npx shadcn@latest add button card badge skeleton input label --yes
```

Set `"name": "frontend"` in `package.json`. Scripts:

```json
{
  "dev": "vite --host 0.0.0.0",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "typecheck": "tsc -b --noEmit",
  "test": "vitest run",
  "gen:api": "openapi-typescript ../backend/openapi.json -o src/api/schema.d.ts"
}
```

Add to `eslint.config.js` a rule that blocks raw `fetch` outside `src/api/client.ts`:

```js
{
  files: ["src/**/*.{ts,tsx}"],
  ignores: ["src/api/client.ts", "src/test/**"],
  rules: {
    "no-restricted-globals": ["error", { name: "fetch", message: "Use the typed api client in src/api/client.ts" }],
  },
},
```

- [ ] **Step 2: Write the failing tests**

`src/api/errors.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { toApiError } from "./errors";

describe("toApiError", () => {
  it("uses FastAPI detail strings", () => {
    const err = toApiError(new Response(null, { status: 402 }), { detail: "no subscription" });
    expect(err.status).toBe(402);
    expect(err.detail).toBe("no subscription");
  });
  it("joins validation errors", () => {
    const err = toApiError(new Response(null, { status: 422 }), { detail: [{ msg: "too short" }, { msg: "bad" }] });
    expect(err.detail).toBe("too short; bad");
  });
  it("falls back to the status text", () => {
    const err = toApiError(new Response(null, { status: 503, statusText: "Service Unavailable" }), null);
    expect(err.detail).toBe("Service Unavailable");
  });
});
```

`src/components/ErrorState.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ApiError } from "@/api/errors";
import { ErrorState } from "./ErrorState";
import { Unavailable } from "./Unavailable";

it("shows status and detail", () => {
  render(<ErrorState error={new ApiError(503, "Lago is unavailable")} />);
  expect(screen.getByText("503")).toBeInTheDocument();
  expect(screen.getByText("Lago is unavailable")).toBeInTheDocument();
});

it("unavailable never renders zero", () => {
  render(<Unavailable />);
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.queryByText("0")).toBeNull();
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npm test`
Expected: FAIL — cannot resolve `./errors`.

- [ ] **Step 4: Implement**

`src/api/errors.ts`:

```ts
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

export function toApiError(response: Response, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(response.status, detail);
  if (Array.isArray(detail)) {
    return new ApiError(response.status, detail.map((d) => (d as { msg?: string }).msg ?? "invalid").join("; "));
  }
  return new ApiError(response.status, response.statusText || "Request failed");
}
```

`src/api/client.ts`:

```ts
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

let tokenProvider: () => Promise<string | null> = async () => null;
export function setTokenProvider(fn: () => Promise<string | null>) {
  tokenProvider = fn;
}

const auth: Middleware = {
  async onRequest({ request }) {
    const token = await tokenProvider();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_BASE_URL });
api.use(auth);
```

`src/api/queries.ts`:

```ts
import { queryOptions } from "@tanstack/react-query";
import { api } from "./client";
import { toApiError } from "./errors";

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || data === undefined) throw toApiError(response, error ?? null);
  return data;
}

export const meQuery = queryOptions({ queryKey: ["me"], queryFn: () => unwrap(api.GET("/me")) });
export const accessQuery = queryOptions({ queryKey: ["access"], queryFn: () => unwrap(api.GET("/me/access")) });
export const plansQuery = queryOptions({ queryKey: ["plans"], queryFn: () => unwrap(api.GET("/billing/plans")) });
export const premiumReportQuery = queryOptions({
  queryKey: ["premium-report"],
  queryFn: () => unwrap(api.GET("/demo/premium-report")),
  retry: false,
});

export const createWorkspace = (name: string) => unwrap(api.POST("/workspaces", { body: { name } }));
export const startCheckout = (plan_code: string) => unwrap(api.POST("/billing/checkout", { body: { plan_code } }));
```

`src/components/ErrorState.tsx`:

```tsx
import type { ApiError } from "@/api/errors";

export function ErrorState({ error }: { error: ApiError }) {
  return (
    <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
      <p className="font-mono text-destructive">{error.status}</p>
      <p className="text-muted-foreground">{error.detail}</p>
    </div>
  );
}
```

`src/components/Unavailable.tsx`:

```tsx
export function Unavailable() {
  return <span className="text-muted-foreground italic">Unavailable</span>;
}
```

`src/components/PageSkeleton.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function PageSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
```

`src/index.css`: `@import "tailwindcss";` then `@import "./brand.css";` followed by the shadcn theme block that maps `--primary`, `--accent`, `--background`, `--foreground` etc. to the `--brand-*` variables (Task 10 defines them). `src/brand.css` placeholder:

```css
/* Generated by `make brand` from brand/brand.yaml. Do not edit by hand. */
:root { --brand-primary: #2f6bff; --brand-accent: #ff7a33; --brand-font: "Inter", system-ui, sans-serif; }
.dark { --brand-primary: #6f97ff; --brand-accent: #ff9a63; }
```

`src/test/setup.ts`: `import "@testing-library/jest-dom/vitest";`. `vite.config.ts` sets `test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"] }` and the `@` alias to `src`.

`src/test/utils.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

export function renderWithQuery(ui: ReactElement, path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export function mockFetch(routes: Record<string, { status: number; body: unknown }>) {
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(input, init);
    const key = `${req.method} ${new URL(req.url).pathname}`;
    const route = routes[key];
    if (!route) return new Response(JSON.stringify({ detail: `no mock for ${key}` }), { status: 599 });
    return new Response(JSON.stringify(route.body), {
      status: route.status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}
```

Run `npm run gen:api` to create `src/api/schema.d.ts` from Task 7's `openapi.json`.

- [ ] **Step 5: Run checks**

Run: `npm run lint && npm run typecheck && npm test && npm run build`
Expected: all pass; 5 tests passed.

- [ ] **Step 6: Commit**

```bash
git add template/frontend
git commit -m "feat(frontend): Vite + shadcn foundation, typed client, error and empty states"
```

---

### Task 10: Frontend sign-in and pages

**Files:**
- Create: `template/frontend/src/auth/userManager.ts`, `src/auth/AuthGate.tsx`, `src/App.tsx`, `src/routes.tsx`, `src/pages/CreateWorkspace.tsx`, `Plans.tsx`, `Billing.tsx`, `PremiumReport.tsx`, `CheckoutReturn.tsx` and a `.test.tsx` beside each page
- Modify: `src/main.tsx`

**Interfaces:**
- Consumes: queries and mutations from Task 9; env `VITE_ZITADEL_ISSUER`, `VITE_ZITADEL_CLIENT_ID`, `VITE_ZITADEL_PROJECT_ID`, `VITE_API_BASE_URL`.
- Produces:
  - `userManager` (oidc-client-ts) with `redirect_uri = ${origin}/callback`, scope `openid profile email offline_access urn:zitadel:iam:org:project:id:${projectId}:aud urn:zitadel:iam:org:projects:roles`.
  - `AuthGate` renders the app only when signed in; otherwise a sign-in screen with one "Sign in" button (`signinRedirect`). After `POST /workspaces` the page calls `userManager.signinSilent()` so the new role appears in the token.
  - Routes: `/` → redirect by state (no workspace → `/workspace/new`; no plan → `/plans`; else `/premium`), `/workspace/new`, `/plans`, `/billing`, `/billing/return`, `/premium`, `/callback`.
  - `CheckoutReturn` polls `accessQuery` every 2 s for up to 60 s and shows "Waiting for payment confirmation…" until `state === "active"`, then links to `/premium`. It never treats the return itself as success.

- [ ] **Step 1: Write the failing tests**

`src/pages/PremiumReport.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { PremiumReport } from "./PremiumReport";

afterEach(() => vi.unstubAllGlobals());

it("shows the report when allowed", async () => {
  mockFetch({ "GET /demo/premium-report": { status: 200, body: { title: "Premium report", generated_for: "Acme" } } });
  renderWithQuery(<PremiumReport />);
  expect(await screen.findByText("Premium report")).toBeInTheDocument();
  expect(screen.getByText(/Acme/)).toBeInTheDocument();
});

it("shows the upgrade path on 402", async () => {
  mockFetch({ "GET /demo/premium-report": { status: 402, body: { detail: "no subscription" } } });
  renderWithQuery(<PremiumReport />);
  expect(await screen.findByText("no subscription")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/plans");
});
```

`src/pages/CheckoutReturn.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CheckoutReturn } from "./CheckoutReturn";

afterEach(() => vi.unstubAllGlobals());

it("waits while pending", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {} } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
});

it("confirms when active", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "active", features: { premium_report: true } } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByRole("link", { name: "Open premium report" })).toBeInTheDocument();
});
```

`src/pages/Plans.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Plans } from "./Plans";

afterEach(() => vi.unstubAllGlobals());

it("lists plans and starts checkout", async () => {
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  mockFetch({
    "GET /billing/plans": { status: 200, body: [{ code: "starter", name: "Starter", amount_cents: 2900, currency: "USD", interval: "month", features: { premium_report: true } }] },
    "POST /billing/checkout": { status: 200, body: { checkout_url: "https://checkout.stripe.test/s" } },
  });
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/s"));
  expect(screen.getByText("$29.00 / month")).toBeInTheDocument();
});

it("shows the API error when checkout fails", async () => {
  mockFetch({
    "GET /billing/plans": { status: 200, body: [{ code: "starter", name: "Starter", amount_cents: 2900, currency: "USD", interval: "month", features: {} }] },
    "POST /billing/checkout": { status: 503, body: { detail: "Lago is unavailable" } },
  });
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  expect(await screen.findByText("Lago is unavailable")).toBeInTheDocument();
});
```

`src/pages/CreateWorkspace.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CreateWorkspace } from "./CreateWorkspace";

vi.mock("@/auth/userManager", () => ({ userManager: { signinSilent: vi.fn(async () => null) } }));
afterEach(() => vi.unstubAllGlobals());

it("creates the workspace then refreshes the token", async () => {
  const { userManager } = await import("@/auth/userManager");
  mockFetch({ "POST /workspaces": { status: 201, body: { id: "w1", name: "Acme", status: "ready" } } });
  renderWithQuery(<CreateWorkspace />);
  fireEvent.change(screen.getByLabelText("Workspace name"), { target: { value: "Acme" } });
  fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
  await vi.waitFor(() => expect(userManager.signinSilent).toHaveBeenCalled());
});

it("disables submit for a blank name", () => {
  renderWithQuery(<CreateWorkspace />);
  expect(screen.getByRole("button", { name: "Create workspace" })).toBeDisabled();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test`
Expected: FAIL — cannot resolve `./PremiumReport`.

- [ ] **Step 3: Implement**

`src/auth/userManager.ts`:

```ts
import { UserManager, WebStorageStateStore } from "oidc-client-ts";

const projectId = import.meta.env.VITE_ZITADEL_PROJECT_ID;

export const userManager = new UserManager({
  authority: import.meta.env.VITE_ZITADEL_ISSUER,
  client_id: import.meta.env.VITE_ZITADEL_CLIENT_ID,
  redirect_uri: `${window.location.origin}/callback`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: `openid profile email offline_access urn:zitadel:iam:org:project:id:${projectId}:aud urn:zitadel:iam:org:projects:roles`,
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  automaticSilentRenew: true,
});

export async function accessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}
```

`src/auth/AuthGate.tsx`:

```tsx
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/PageSkeleton";
import { userManager } from "./userManager";

export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "in" | "out">("loading");
  useEffect(() => {
    const run = async () => {
      if (window.location.pathname === "/callback") {
        await userManager.signinRedirectCallback();
        window.history.replaceState({}, "", "/");
      }
      const user = await userManager.getUser();
      setState(user && !user.expired ? "in" : "out");
    };
    run().catch(() => setState("out"));
  }, []);
  if (state === "loading") return <PageSkeleton />;
  if (state === "out") {
    return (
      <main className="mx-auto mt-24 max-w-sm space-y-4 text-center">
        <h1 className="text-xl font-semibold">{import.meta.env.VITE_PRODUCT_NAME}</h1>
        <Button onClick={() => userManager.signinRedirect()}>Sign in</Button>
      </main>
    );
  }
  return <>{children}</>;
}
```

`src/pages/PremiumReport.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { premiumReportQuery } from "@/api/queries";
import { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";

export function PremiumReport() {
  const { data, error, isPending } = useQuery(premiumReportQuery);
  if (isPending) return <PageSkeleton />;
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorState error={error as ApiError} />
        {(error as ApiError).status === 402 && <Link to="/plans" className="text-primary underline">See plans</Link>}
      </div>
    );
  }
  return (
    <article className="space-y-2">
      <h1 className="text-lg font-semibold">{data.title}</h1>
      <p className="text-sm text-muted-foreground">Generated for {data.generated_for}</p>
    </article>
  );
}
```

`src/pages/CheckoutReturn.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { accessQuery } from "@/api/queries";
import { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";

export function CheckoutReturn() {
  const startedAt = Date.now();
  const { data, error } = useQuery({
    ...accessQuery,
    refetchInterval: (q) => (q.state.data?.state === "active" || Date.now() - startedAt > 60_000 ? false : 2_000),
  });
  if (error) return <ErrorState error={error as ApiError} />;
  if (data?.state === "active") {
    return (
      <div className="space-y-2">
        <p>Your plan is active.</p>
        <Link to="/premium" className="text-primary underline">Open premium report</Link>
      </div>
    );
  }
  return <p className="text-sm text-muted-foreground">Waiting for payment confirmation…</p>;
}
```

`src/pages/Plans.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { plansQuery, startCheckout } from "@/api/queries";
import { ApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";

const money = (cents: number, currency: string) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);

export function Plans() {
  const plans = useQuery(plansQuery);
  const checkout = useMutation({
    mutationFn: startCheckout,
    onSuccess: ({ checkout_url }) => window.location.assign(checkout_url),
  });
  if (plans.isPending) return <PageSkeleton />;
  if (plans.error) return <ErrorState error={plans.error as ApiError} />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {checkout.error && <ErrorState error={checkout.error as ApiError} />}
      {plans.data.map((p) => (
        <Card key={p.code}>
          <CardHeader><CardTitle>{p.name}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{money(p.amount_cents, p.currency)} / {p.interval}</p>
            <Button disabled={checkout.isPending} onClick={() => checkout.mutate(p.code)}>Choose {p.name}</Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

`src/pages/CreateWorkspace.tsx`:

```tsx
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { createWorkspace } from "@/api/queries";
import { ApiError } from "@/api/errors";
import { userManager } from "@/auth/userManager";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/ErrorState";

export function CreateWorkspace() {
  const [name, setName] = useState("");
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: createWorkspace,
    onSuccess: async () => {
      await userManager.signinSilent();
      navigate("/plans");
    },
  });
  return (
    <form className="max-w-sm space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(name.trim()); }}>
      <Label htmlFor="ws-name">Workspace name</Label>
      <Input id="ws-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
      {create.error && <ErrorState error={create.error as ApiError} />}
      <Button type="submit" disabled={!name.trim() || create.isPending}>Create workspace</Button>
    </form>
  );
}
```

`src/pages/Billing.tsx` shows `accessQuery`: plan code, state, and features; `null` plan → "No plan yet" plus a link to `/plans`; uses `Unavailable` for a missing `current_period_end`. Its test (`Billing.test.tsx`) mocks `/me/access` with `{ plan_code: null, state: null, features: {} }` and expects the text "No plan yet" and a link "See plans".

`src/routes.tsx` and `src/App.tsx`: `createBrowserRouter` with the routes above; `/` is a `Home` component that reads `meQuery` then `accessQuery` and `<Navigate>`s per the rule in Interfaces. `src/main.tsx` calls `setTokenProvider(accessToken)`, wraps in `QueryClientProvider` and `AuthGate`.

- [ ] **Step 4: Run checks**

Run: `npm run lint && npm run typecheck && npm test && npm run build`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add template/frontend
git commit -m "feat(frontend): Zitadel sign-in, workspace, plans, checkout return, premium page"
```

---

### Task 11: Branding — one file drives the app, Zitadel and Lago

**Files:**
- Create: `template/brand/brand.yaml.jinja`, `template/brand/logo.svg`, `template/scripts/brand.py`, `template/scripts/tests/test_brand.py`, `template/scripts/pyproject.toml`
- Delete: `template/brand/.gitkeep`

**Interfaces:**
- Consumes: Zitadel admin token (`.bootstrap/admin.pat`), Lago GraphQL session (from Task 12 bootstrap helper `lago_graphql_login()`).
- Produces:
  - Lago's `UpdateOrganizationInput` has `legalName` and `logo` (base64 data URL), not `name` (checked in lago-api 2026-10-31).
  - `scripts/brand.py`: `load_brand(path) -> Brand`, `css_tokens(brand) -> str`, `zitadel_label_policy(brand) -> dict`, `apply_zitadel(brand, api_url, token)`, `apply_lago(brand, graphql)`, CLI `python scripts/brand.py [--css-only]`.
  - `Brand(name, logo_path, font, light: Palette, dark: Palette)`; `Palette(primary, accent, background, foreground, warn)`.
  - Dark palette is computed when not given: primary and accent lightened 25%, background `#0b0b0c`, foreground `#ececee`.

- [ ] **Step 1: Write the failing tests**

`template/scripts/tests/test_brand.py`:

```python
import pathlib

import pytest

from brand import BrandError, css_tokens, load_brand, zitadel_label_policy


def write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    (tmp_path / "logo.svg").write_text("<svg/>")
    p = tmp_path / "brand.yaml"
    p.write_text(text)
    return p


def test_css_has_light_and_dark(tmp_path: pathlib.Path) -> None:
    brand = load_brand(write(tmp_path, "name: Acme\nfont: Inter\nlogo: logo.svg\nlight: {primary: '#3355ff', accent: '#ff7a33'}\n"))
    css = css_tokens(brand)
    assert "--brand-primary: #3355ff;" in css
    assert ".dark {" in css
    assert '--brand-font: "Inter", system-ui, sans-serif;' in css


def test_zitadel_policy_maps_colours(tmp_path: pathlib.Path) -> None:
    brand = load_brand(write(tmp_path, "name: Acme\nfont: Inter\nlogo: logo.svg\nlight: {primary: '#3355ff', accent: '#ff7a33'}\n"))
    policy = zitadel_label_policy(brand)
    assert policy["primaryColor"] == "#3355ff"
    assert policy["backgroundColorDark"] == "#0b0b0c"
    assert policy["hideLoginNameSuffix"] is True


@pytest.mark.parametrize("bad", ["'#33f'", "'blue'", "'#3355ffaa'"])
def test_bad_colours_rejected(tmp_path: pathlib.Path, bad: str) -> None:
    with pytest.raises(BrandError, match="colour"):
        load_brand(write(tmp_path, f"name: Acme\nfont: Inter\nlogo: logo.svg\nlight: {{primary: {bad}, accent: '#ff7a33'}}\n"))


def test_missing_logo_rejected(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "brand.yaml"
    p.write_text("name: Acme\nfont: Inter\nlogo: nope.svg\nlight: {primary: '#3355ff', accent: '#ff7a33'}\n")
    with pytest.raises(BrandError, match="logo"):
        load_brand(p)
```

- [ ] **Step 2: Run to verify failure**

Run: `make dev && cd .dev/acme/scripts && uv run pytest -q`
Expected: FAIL — `No module named 'brand'`.

- [ ] **Step 3: Implement**

`template/scripts/pyproject.toml`:

```toml
[project]
name = "scripts"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["httpx>=0.28", "pyyaml>=6.0"]
[dependency-groups]
dev = ["pytest>=8.3", "respx>=0.21"]
[tool.pytest.ini_options]
pythonpath = ["."]
```

`template/brand/brand.yaml.jinja`:

```yaml
name: {{ product_name }}
font: {{ brand_font }}
logo: logo.svg
light:
  primary: "{{ brand_primary }}"
  accent: "{{ brand_accent }}"
# dark: optional; computed from light when omitted
```

`template/brand/logo.svg`: a simple 64×64 rounded square with the letter "C" in `currentColor` (replace per product).

`template/scripts/brand.py`:

```python
import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ROOT = Path(__file__).resolve().parents[1]


class BrandError(ValueError):
    pass


@dataclass(frozen=True)
class Palette:
    primary: str
    accent: str
    background: str
    foreground: str
    warn: str = "#d93025"


@dataclass(frozen=True)
class Brand:
    name: str
    font: str
    logo_path: Path
    light: Palette
    dark: Palette


def _colour(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX.match(value):
        raise BrandError(f"{field}: colour must be like #3355ff")
    return value.lower()


def _lighten(hex_colour: str, amount: float = 0.25) -> str:
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def load_brand(path: Path) -> Brand:
    raw = yaml.safe_load(path.read_text())
    logo = path.parent / str(raw["logo"])
    if not logo.exists():
        raise BrandError(f"logo file {logo.name} not found")
    light_raw = raw["light"]
    light = Palette(_colour(light_raw["primary"], "light.primary"), _colour(light_raw["accent"], "light.accent"),
                    _colour(light_raw.get("background", "#ffffff"), "light.background"),
                    _colour(light_raw.get("foreground", "#111114"), "light.foreground"))
    dark_raw = raw.get("dark") or {}
    dark = Palette(_colour(dark_raw.get("primary", _lighten(light.primary)), "dark.primary"),
                   _colour(dark_raw.get("accent", _lighten(light.accent)), "dark.accent"),
                   _colour(dark_raw.get("background", "#0b0b0c"), "dark.background"),
                   _colour(dark_raw.get("foreground", "#ececee"), "dark.foreground"))
    return Brand(str(raw["name"]), str(raw["font"]), logo, light, dark)


def css_tokens(brand: Brand) -> str:
    def block(selector: str, p: Palette) -> str:
        return (f"{selector} {{\n  --brand-primary: {p.primary};\n  --brand-accent: {p.accent};\n"
                f"  --brand-background: {p.background};\n  --brand-foreground: {p.foreground};\n")
    font = f'  --brand-font: "{brand.font}", system-ui, sans-serif;\n'
    return ("/* Generated by `make brand` from brand/brand.yaml. Do not edit by hand. */\n"
            + block(":root", brand.light) + font + "}\n" + block(".dark", brand.dark) + "}\n")


def zitadel_label_policy(brand: Brand) -> dict[str, Any]:
    return {
        "primaryColor": brand.light.primary, "backgroundColor": brand.light.background,
        "warnColor": brand.light.warn, "fontColor": brand.light.foreground,
        "primaryColorDark": brand.dark.primary, "backgroundColorDark": brand.dark.background,
        "warnColorDark": brand.dark.warn, "fontColorDark": brand.dark.foreground,
        "hideLoginNameSuffix": True, "disableWatermark": True,
    }


def apply_zitadel(brand: Brand, api_url: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=api_url, headers=headers, timeout=15.0) as http:
        http.put("/admin/v1/policies/label", json=zitadel_label_policy(brand)).raise_for_status()
        for variant in ("logo", "logo/dark"):
            files = {"file": (brand.logo_path.name, brand.logo_path.read_bytes(), "image/svg+xml")}
            http.post(f"/assets/v1/instance/policy/label/{variant}", files=files).raise_for_status()
        http.post("/admin/v1/policies/label/_activate", json={}).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--css-only", action="store_true")
    args = parser.parse_args()
    brand = load_brand(ROOT / "brand" / "brand.yaml")
    (ROOT / "frontend" / "src" / "brand.css").write_text(css_tokens(brand))
    print("wrote frontend/src/brand.css")
    if args.css_only:
        return
    from bootstrap import env, lago_graphql, zitadel_admin_token  # Task 12

    apply_zitadel(brand, env("ZITADEL_PUBLIC_URL"), zitadel_admin_token())
    lago_graphql("mutation($i: UpdateOrganizationInput!){updateOrganization(input:$i){id}}",
                 {"i": {"legalName": brand.name, "logo": "data:image/svg+xml;base64,"
                        + __import__("base64").b64encode(brand.logo_path.read_bytes()).decode()}})
    print("applied brand to Zitadel and Lago")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `make dev && cd .dev/acme/scripts && uv lock && cp uv.lock ../../../template/scripts/ && uv run pytest -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add template/brand template/scripts
git commit -m "feat(brand): brand.yaml generates CSS tokens and Zitadel/Lago branding"
```

---

### Task 12: Docker Compose, bootstrap and doctor

**Files:**
- Create: `template/docker-compose.yml.jinja`, `template/.env.example.jinja`, `template/Makefile.jinja`, `template/scripts/postgres-init.sql.jinja`, `template/scripts/bootstrap.py`, `template/scripts/doctor.py`, `template/scripts/tests/test_bootstrap.py`, `template/scripts/smoke_zitadel.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `make up` / `down` / `bootstrap` / `brand` / `sync-plans` / `migrate` / `check` / `e2e` / `doctor` / `logs`.
  - `scripts/bootstrap.py` functions used by `brand.py`: `env(name: str) -> str`, `zitadel_admin_token() -> str`, `lago_graphql(query: str, variables: dict) -> dict`.
  - Bootstrap writes non-secret IDs to `.bootstrap/ids.env` (git-ignored): `ZITADEL_PROJECT_ID`, `ZITADEL_INSTANCE_ORG_ID`, `ZITADEL_CLIENT_ID`, `ZITADEL_SERVICE_TOKEN_FILE`. Compose reads it via `env_file`.
  - Local hostnames (all resolve to 127.0.0.1 via `*.localhost`): app `http://{{domain}}:5173`, API `http://api.{{domain}}:8000`, Zitadel `http://auth.{{domain}}:8080`, Lago API `http://lago-api.{{domain}}:3000`, Lago UI `http://lago.{{domain}}:8088`, MinIO console `:9001`.

**Bootstrap steps (idempotent, each checks before creating):**

1. Wait for `GET {zitadel}/debug/ready`, Lago `GET /health`, Postgres, MinIO.
2. Zitadel, using the admin PAT that `ZITADEL_FIRSTINSTANCE_PATPATH` wrote to the `zitadel-bootstrap` volume:
   - read the instance org id (`GET /management/v1/orgs/me`);
   - create project `{{ product_slug }}` with `projectRoleAssertion: true`; add roles `owner`, `member`;
   - create OIDC app `web` (`POST /management/v1/projects/{id}/apps/oidc`): `redirectUris` `[http://{{domain}}:5173/callback]`, `postLogoutRedirectUris` `[http://{{domain}}:5173/]`, `responseTypes` `[OIDC_RESPONSE_TYPE_CODE]`, `grantTypes` `[AUTHORIZATION_CODE, REFRESH_TOKEN]`, `appType` `OIDC_APP_TYPE_USER_AGENT`, `authMethodType` `OIDC_AUTH_METHOD_TYPE_NONE`, `accessTokenType` `OIDC_TOKEN_TYPE_JWT`, `accessTokenRoleAssertion: true`, `idTokenRoleAssertion: true`, `devMode: true` (allows http);
   - create machine user `backend` with a PAT and grant it `ORG_OWNER` on the instance org (`POST /admin/v1/members` with role `IAM_ORG_MANAGER` so it can create orgs) — PAT written to `.bootstrap/backend.pat` (git-ignored, mounted read-only into the backend);
   - enable self-registration in the login policy (`PUT /admin/v1/policies/login` `allowRegister: true`).
3. Lago (org seeded by `LAGO_CREATE_ORG=true` + `LAGO_ORG_API_KEY`):
   - log in via GraphQL `loginUser` with `LAGO_ORG_USER_EMAIL`/`PASSWORD`, read the organization id;
   - add the Stripe provider: `addStripePaymentProvider(input: {name: "Stripe", code: "stripe", secretKey: $STRIPE_SECRET_KEY, successRedirectUrl: "http://{{domain}}:5173/billing/return"})` (skip if `paymentProvider(code: "stripe")` exists);
   - Lago cannot register a Stripe endpoint for a `localhost` URL, so set the webhook secret Lago checks to the Stripe CLI's: `docker compose exec -T lago-api bin/rails runner 'PaymentProviders::StripeProvider.find_by!(code: "stripe").update!(webhook_secret: ENV.fetch("STRIPE_CLI_WEBHOOK_SECRET"))'` where the secret comes from `docker compose run --rm stripe-cli listen --print-secret`;
   - create the webhook endpoint to the backend: `POST /api/v1/webhook_endpoints {"webhook_endpoint": {"webhook_url": "http://backend:8000/billing/webhooks/lago", "signature_algo": "jwt"}}` (Lago has `LAGO_WEBHOOK_ALLOW_PRIVATE_URLS=true`);
   - create billable metric `reports_generated` (`aggregation_type: count_agg`).
4. Run backend migrations (`alembic upgrade head`), then `python -m app.billing.sync`, then `scripts/brand.py`.
5. Print the URLs and "open http://{{domain}}:5173".

- [ ] **Step 1: Write the failing tests** (pure helpers only; Compose is covered by e2e)

`template/scripts/tests/test_bootstrap.py`:

```python
import pathlib

import httpx
import pytest
import respx

from bootstrap import ensure_project, read_ids, write_ids


def test_ids_roundtrip(tmp_path: pathlib.Path) -> None:
    write_ids(tmp_path / "ids.env", {"ZITADEL_PROJECT_ID": "p1", "ZITADEL_CLIENT_ID": "c1"})
    assert read_ids(tmp_path / "ids.env") == {"ZITADEL_PROJECT_ID": "p1", "ZITADEL_CLIENT_ID": "c1"}


@respx.mock
def test_ensure_project_reuses_existing() -> None:
    respx.post("http://z/management/v1/projects/_search").respond(
        200, json={"result": [{"id": "p1", "name": "acme"}]})
    create = respx.post("http://z/management/v1/projects").respond(200, json={"id": "p2"})
    with httpx.Client(base_url="http://z") as http:
        assert ensure_project(http, "acme") == "p1"
    assert create.call_count == 0


@respx.mock
def test_ensure_project_creates_with_role_assertion() -> None:
    respx.post("http://z/management/v1/projects/_search").respond(200, json={"result": []})
    create = respx.post("http://z/management/v1/projects").respond(200, json={"id": "p2"})
    roles = respx.post("http://z/management/v1/projects/p2/roles/_bulk").respond(200, json={})
    with httpx.Client(base_url="http://z") as http:
        assert ensure_project(http, "acme") == "p2"
    assert b'"projectRoleAssertion": true' in create.calls.last.request.content.replace(b'":true', b'": true')
    assert b"owner" in roles.calls.last.request.content


def test_env_missing_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    from bootstrap import env
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(SystemExit, match="STRIPE_SECRET_KEY"):
        env("STRIPE_SECRET_KEY")
```

- [ ] **Step 2: Run to verify failure**

Run: `make dev && cd .dev/acme/scripts && uv run pytest tests/test_bootstrap.py -q`
Expected: FAIL — `No module named 'bootstrap'`.

- [ ] **Step 3: Implement `scripts/bootstrap.py`**

```python
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".bootstrap"
IDS = STATE / "ids.env"


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set; copy .env.example to .env and fill it in")
    return value


def write_ids(path: Path, ids: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in ids.items()))


def read_ids(path: Path = IDS) -> dict[str, str]:
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def wait_for(url: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=3.0).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit(f"timed out waiting for {url}")


def compose(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, text=True,
                            capture_output=capture)
    return result.stdout.strip() if capture else ""


def zitadel_admin_token() -> str:
    return compose("exec", "-T", "zitadel-api", "cat", "/zitadel/bootstrap/admin.pat", capture=True)


def zitadel_http() -> httpx.Client:
    return httpx.Client(base_url=env("ZITADEL_PUBLIC_URL"),
                        headers={"Authorization": f"Bearer {zitadel_admin_token()}"}, timeout=15.0)


def ensure_project(http: httpx.Client, name: str) -> str:
    found = http.post("/management/v1/projects/_search",
                      json={"queries": [{"nameQuery": {"name": name, "method": "TEXT_QUERY_METHOD_EQUALS"}}]})
    found.raise_for_status()
    for project in found.json().get("result", []):
        if project["name"] == name:
            return str(project["id"])
    created = http.post("/management/v1/projects", json={"name": name, "projectRoleAssertion": True})
    created.raise_for_status()
    project_id = str(created.json()["id"])
    http.post(f"/management/v1/projects/{project_id}/roles/_bulk", json={"roles": [
        {"key": "owner", "displayName": "Owner"}, {"key": "member", "displayName": "Member"}]}).raise_for_status()
    return project_id


def ensure_web_app(http: httpx.Client, project_id: str, app_url: str) -> str:
    existing = http.post(f"/management/v1/projects/{project_id}/apps/_search", json={})
    existing.raise_for_status()
    for app in existing.json().get("result", []):
        if app["name"] == "web":
            return str(app["oidcConfig"]["clientId"])
    created = http.post(f"/management/v1/projects/{project_id}/apps/oidc", json={
        "name": "web",
        "redirectUris": [f"{app_url}/callback"],
        "postLogoutRedirectUris": [f"{app_url}/"],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_USER_AGENT",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": True,
        "idTokenRoleAssertion": True,
        "devMode": True,
    })
    created.raise_for_status()
    return str(created.json()["clientId"])


def ensure_backend_machine_user(http: httpx.Client) -> None:
    target = STATE / "backend.pat"
    if target.exists():
        return
    user = http.post("/management/v1/users/machine", json={
        "userName": "backend", "name": "Backend", "accessTokenType": "ACCESS_TOKEN_TYPE_BEARER"})
    if user.status_code == 409:
        found = http.post("/management/v1/users/_search", json={"queries": [
            {"userNameQuery": {"userName": "backend", "method": "TEXT_QUERY_METHOD_EQUALS"}}]})
        user_id = found.json()["result"][0]["id"]
    else:
        user.raise_for_status()
        user_id = user.json()["userId"]
    http.post("/admin/v1/members", json={"userId": user_id, "roles": ["IAM_OWNER"]})
    pat = http.post(f"/management/v1/users/{user_id}/pats", json={})
    pat.raise_for_status()
    target.write_text(pat.json()["token"])
    target.chmod(0o600)


def lago_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    url = f"{env('LAGO_PUBLIC_API_URL')}/graphql"
    login = httpx.post(url, json={"query": "mutation($i: LoginUserInput!){loginUser(input:$i){token user{organizations{id}}}}",
                                  "variables": {"i": {"email": env("LAGO_ORG_USER_EMAIL"),
                                                      "password": env("LAGO_ORG_USER_PASSWORD")}}}).json()
    data = login["data"]["loginUser"]
    headers = {"Authorization": f"Bearer {data['token']}",
               "x-lago-organization": data["user"]["organizations"][0]["id"]}
    result = httpx.post(url, json={"query": query, "variables": variables}, headers=headers, timeout=30.0).json()
    if result.get("errors"):
        raise SystemExit(f"Lago GraphQL error: {json.dumps(result['errors'])}")
    data_out: dict[str, Any] = result["data"]
    return data_out


def ensure_lago(app_url: str) -> None:
    existing = lago_graphql("query{paymentProvider(code:\"stripe\"){... on StripeProvider{id}}}", {})
    if not existing.get("paymentProvider"):
        lago_graphql("mutation($i: AddStripePaymentProviderInput!){addStripePaymentProvider(input:$i){id}}",
                     {"i": {"name": "Stripe", "code": "stripe", "secretKey": env("STRIPE_SECRET_KEY"),
                            "successRedirectUrl": f"{app_url}/billing/return"}})
    secret = compose("run", "--rm", "stripe-cli", "listen", "--print-secret", capture=True).splitlines()[-1]
    ruby = ('PaymentProviders::StripeProvider.find_by!(code: "stripe")'
            f'.update!(webhook_secret: "{secret}")')
    compose("exec", "-T", "lago-api", "bin/rails", "runner", ruby)
    api = httpx.Client(base_url=env("LAGO_PUBLIC_API_URL"),
                       headers={"Authorization": f"Bearer {env('LAGO_API_KEY')}"}, timeout=15.0)
    hooks = api.get("/api/v1/webhook_endpoints").json().get("webhook_endpoints", [])
    target = "http://backend:8000/billing/webhooks/lago"
    if not any(h["webhook_url"] == target for h in hooks):
        api.post("/api/v1/webhook_endpoints", json={"webhook_endpoint": {
            "webhook_url": target, "signature_algo": "jwt"}}).raise_for_status()
    metric = api.get("/api/v1/billable_metrics/reports_generated")
    if metric.status_code == 404:
        api.post("/api/v1/billable_metrics", json={"billable_metric": {
            "name": "Reports generated", "code": "reports_generated", "aggregation_type": "count_agg"}}).raise_for_status()


def main() -> None:
    app_url = env("APP_URL")
    wait_for(f"{env('ZITADEL_PUBLIC_URL')}/debug/ready")
    wait_for(f"{env('LAGO_PUBLIC_API_URL')}/health")
    with zitadel_http() as http:
        org_id = str(http.get("/management/v1/orgs/me").json()["org"]["id"])
        project_id = ensure_project(http, env("PRODUCT_SLUG"))
        client_id = ensure_web_app(http, project_id, app_url)
        ensure_backend_machine_user(http)
        http.put("/admin/v1/policies/login", json={"allowRegister": True, "allowUsernamePassword": True})
    write_ids(IDS, {"ZITADEL_PROJECT_ID": project_id, "ZITADEL_INSTANCE_ORG_ID": org_id,
                    "ZITADEL_CLIENT_ID": client_id})
    ensure_lago(app_url)
    compose("up", "-d", "--force-recreate", "backend", "frontend", "jobs")
    compose("exec", "-T", "backend", "uv", "run", "alembic", "upgrade", "head")
    compose("exec", "-T", "backend", "uv", "run", "python", "-m", "app.billing.sync")
    subprocess.run(["uv", "run", "python", "brand.py"], cwd=ROOT / "scripts", check=True)
    print(f"Ready: open {app_url}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write Compose, env and Makefile**

`template/scripts/postgres-init.sql.jinja`:

```sql
CREATE USER app WITH PASSWORD 'app';
CREATE DATABASE app OWNER app;
CREATE DATABASE app_test OWNER app;
CREATE USER zitadel WITH PASSWORD 'zitadel';
CREATE DATABASE zitadel OWNER zitadel;
CREATE USER lago WITH PASSWORD 'lago' SUPERUSER;
CREATE DATABASE lago OWNER lago;
```

(Local-only passwords; real environments get generated secrets in milestone 2.)

`template/.env.example.jinja` (names only for secrets):

```bash
PRODUCT_SLUG={{ product_slug }}
APP_URL=http://{{ domain }}:5173
ZITADEL_PUBLIC_URL=http://auth.{{ domain }}:8080
LAGO_PUBLIC_API_URL=http://lago-api.{{ domain }}:3000
# Stripe test mode only (sk_test_...). Get them from dashboard.stripe.com/test/apikeys
STRIPE_SECRET_KEY=
STRIPE_API_KEY=
# Generate: openssl rand -hex 16  (exactly 32 characters)
ZITADEL_MASTERKEY=
# Generate: openssl rand -base64 32
LOGIN_SESSION_COOKIE_SECRET=
# Generate: openssl rand -hex 64
SECRET_KEY_BASE=
# Generate: openssl genrsa 2048 | openssl base64 -A
LAGO_RSA_PRIVATE_KEY=
# Generate each: openssl rand -hex 16
LAGO_ENCRYPTION_PRIMARY_KEY=
LAGO_ENCRYPTION_DETERMINISTIC_KEY=
LAGO_ENCRYPTION_KEY_DERIVATION_SALT=
LAGO_API_KEY=
LAGO_ORG_USER_EMAIL=admin@{{ domain }}
LAGO_ORG_USER_PASSWORD=
```

Add a `make env` target that fills every blank generated value with `openssl` (never Stripe keys), so the human only pastes the two Stripe test keys.

`template/docker-compose.yml.jinja` — services (all on network `app`; volumes `pg`, `minio`, `zitadel-bootstrap`, `lago-storage`):

```yaml
x-lago-env: &lago-env
  DATABASE_URL: postgresql://lago:lago@postgres:5432/lago
  REDIS_URL: redis://redis:6379
  LAGO_REDIS_CACHE_URL: redis://redis:6379
  SECRET_KEY_BASE: ${SECRET_KEY_BASE}
  LAGO_RSA_PRIVATE_KEY: ${LAGO_RSA_PRIVATE_KEY}
  LAGO_ENCRYPTION_PRIMARY_KEY: ${LAGO_ENCRYPTION_PRIMARY_KEY}
  LAGO_ENCRYPTION_DETERMINISTIC_KEY: ${LAGO_ENCRYPTION_DETERMINISTIC_KEY}
  LAGO_ENCRYPTION_KEY_DERIVATION_SALT: ${LAGO_ENCRYPTION_KEY_DERIVATION_SALT}
  LAGO_API_URL: ${LAGO_PUBLIC_API_URL}
  LAGO_FRONT_URL: http://lago.{{ domain }}:8088
  LAGO_PDF_URL: http://lago-pdf:3000
  LAGO_WEBHOOK_ALLOW_PRIVATE_URLS: "true"
  LAGO_DISABLE_SEGMENT: "true"
  LAGO_CREATE_ORG: "true"
  LAGO_ORG_NAME: {{ product_name }}
  LAGO_ORG_USER_EMAIL: ${LAGO_ORG_USER_EMAIL}
  LAGO_ORG_USER_PASSWORD: ${LAGO_ORG_USER_PASSWORD}
  LAGO_ORG_API_KEY: ${LAGO_API_KEY}
  RAILS_ENV: production
  RAILS_LOG_TO_STDOUT: "true"

services:
  postgres:
    image: getlago/postgres-partman:15.0-alpine
    environment: {POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres}
    volumes: [pg:/var/lib/postgresql/data, ./scripts/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro]
    ports: ["5432:5432"]
    healthcheck: {test: ["CMD", "pg_isready", "-U", "postgres"], interval: 5s, retries: 20}
  redis:
    image: redis:7-alpine
  minio:
    image: minio/minio:RELEASE.2025-09-07T16-13-09Z
    command: server /data --console-address :9001
    environment: {MINIO_ROOT_USER: minio, MINIO_ROOT_PASSWORD: minio-local}
    volumes: [minio:/data]
    ports: ["9000:9000", "9001:9001"]
  zitadel-api:
    image: ghcr.io/zitadel/zitadel:v4.20.0
    user: "0"
    command: start-from-init --masterkey "${ZITADEL_MASTERKEY}"
    environment:
      ZITADEL_PORT: 8080
      ZITADEL_EXTERNALDOMAIN: auth.{{ domain }}
      ZITADEL_EXTERNALPORT: 8080
      ZITADEL_EXTERNALSECURE: "false"
      ZITADEL_TLS_ENABLED: "false"
      ZITADEL_DATABASE_POSTGRES_DSN: postgresql://zitadel:zitadel@postgres:5432/zitadel?sslmode=disable
      ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED: "false"
      ZITADEL_FIRSTINSTANCE_PATPATH: /zitadel/bootstrap/admin.pat
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_USERNAME: bootstrap-admin
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_NAME: Bootstrap admin
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_PAT_EXPIRATIONDATE: "2099-01-01T00:00:00Z"
      ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH: /zitadel/bootstrap/login-client.pat
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_USERNAME: login-client
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_NAME: Login client
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_PAT_EXPIRATIONDATE: "2099-01-01T00:00:00Z"
      ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED: "true"
      ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_BASEURI: http://auth.{{ domain }}:8080/ui/v2/login/
      ZITADEL_OIDC_DEFAULTLOGINURLV2: http://auth.{{ domain }}:8080/ui/v2/login/login?authRequest=
      ZITADEL_OIDC_DEFAULTLOGOUTURLV2: http://auth.{{ domain }}:8080/ui/v2/login/logout?post_logout_redirect=
    volumes: [zitadel-bootstrap:/zitadel/bootstrap]
    ports: ["8080:8080"]
    depends_on: {postgres: {condition: service_healthy}}
    healthcheck: {test: ["CMD", "/app/zitadel", "ready"], interval: 10s, retries: 12, start_period: 20s}
  zitadel-login:
    image: ghcr.io/zitadel/zitadel-login:v4.20.0
    user: "0"
    environment:
      ZITADEL_API_URL: http://zitadel-api:8080
      NEXT_PUBLIC_BASE_PATH: /ui/v2/login
      ZITADEL_SERVICE_USER_TOKEN_FILE: /zitadel/bootstrap/login-client.pat
      ZITADEL_SESSION_COOKIE_SECRET: ${LOGIN_SESSION_COOKIE_SECRET}
      CUSTOM_REQUEST_HEADERS: Host:auth.{{ domain }},X-Forwarded-Proto:http
    volumes: [zitadel-bootstrap:/zitadel/bootstrap:ro]
    network_mode: service:zitadel-api
    depends_on: {zitadel-api: {condition: service_healthy}}
  lago-migrate:
    image: getlago/api:v1.55.0
    command: ["./scripts/migrate.sh"]
    environment: *lago-env
    depends_on: {postgres: {condition: service_healthy}}
  lago-api:
    image: getlago/api:v1.55.0
    command: ["./scripts/start.api.sh"]
    environment: *lago-env
    volumes: [lago-storage:/app/storage]
    ports: ["3000:3000"]
    depends_on: {lago-migrate: {condition: service_completed_successfully}, redis: {condition: service_started}}
  lago-worker:
    image: getlago/api:v1.55.0
    command: ["./scripts/start.worker.sh"]
    environment: *lago-env
    volumes: [lago-storage:/app/storage]
    depends_on: {lago-api: {condition: service_started}}
  lago-clock:
    image: getlago/api:v1.55.0
    command: ["./scripts/start.clock.sh"]
    environment: *lago-env
    depends_on: {lago-api: {condition: service_started}}
  lago-front:
    image: getlago/front:v1.55.0
    environment: {API_URL: "${LAGO_PUBLIC_API_URL}", APP_ENV: production, LAGO_DISABLE_SIGNUP: "true"}
    ports: ["8088:80"]
  lago-pdf:
    image: getlago/lago-gotenberg:7.8.2
  stripe-cli:
    image: stripe/stripe-cli:v1.55.6
    command: listen --forward-to http://lago-api:3000/webhooks/stripe/${LAGO_ORGANIZATION_ID:-unset}?code=stripe
    environment: {STRIPE_API_KEY: "${STRIPE_API_KEY}", STRIPE_DEVICE_NAME: "{{ product_slug }}-local"}
  backend:
    build: ./backend
    env_file: [.env, .bootstrap/ids.env]
    environment:
      DATABASE_URL: postgresql+psycopg://app:app@postgres:5432/app
      FRONTEND_URL: ${APP_URL}
      ZITADEL_ISSUER: ${ZITADEL_PUBLIC_URL}
      ZITADEL_API_URL: http://zitadel-api:8080
      ZITADEL_SERVICE_TOKEN_FILE: /run/secrets/backend.pat
      LAGO_API_URL: http://lago-api:3000
      LAGO_WEBHOOK_ISSUER: ${LAGO_PUBLIC_API_URL}
    volumes: [./.bootstrap/backend.pat:/run/secrets/backend.pat:ro]
    ports: ["8000:8000"]
    depends_on: {postgres: {condition: service_healthy}}
  jobs:
    build: ./jobs
    environment:
      DATABASE_URL: postgresql+psycopg://app:app@postgres:5432/app
      LAGO_API_URL: http://lago-api:3000
      LAGO_API_KEY: ${LAGO_API_KEY}
      S3_ENDPOINT_URL: http://minio:9000
      AWS_ACCESS_KEY_ID: minio
      AWS_SECRET_ACCESS_KEY: minio-local
      RAW_BUCKET: raw
  frontend:
    image: node:22-alpine
    working_dir: /app
    command: sh -c "npm ci && npm run dev"
    env_file: [.bootstrap/ids.env]
    environment:
      VITE_API_BASE_URL: http://api.{{ domain }}:8000
      VITE_ZITADEL_ISSUER: ${ZITADEL_PUBLIC_URL}
      VITE_PRODUCT_NAME: {{ product_name }}
    volumes: [./frontend:/app]
    ports: ["5173:5173"]

volumes: {pg: {}, minio: {}, zitadel-bootstrap: {}, lago-storage: {}}
```

Notes for the implementer, each verified upstream on 2026-10-31:
- Settings reads `zitadel_service_token` from the file: add to `Settings` a `zitadel_service_token_file: str | None = None` and a model validator that loads the token from that file when `zitadel_service_token` is empty. Add a test for it in `tests/test_config.py`.
- Frontend env needs `VITE_`-prefixed IDs: in `vite.config.ts` set `envPrefix: ["VITE_", "ZITADEL_"]` and read `import.meta.env.ZITADEL_CLIENT_ID` / `ZITADEL_PROJECT_ID`; update `userManager.ts` accordingly.
- `stripe-cli` forwards to Lago's Stripe route `POST /webhooks/stripe/:organization_id?code=stripe`; bootstrap writes `LAGO_ORGANIZATION_ID` into `.bootstrap/ids.env` (from the GraphQL login response) and recreates `stripe-cli`.
- Backend CORS: in `create_app()` add `CORSMiddleware(allow_origins=[settings.frontend_url], allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"], allow_methods=["*"])`, with a test that an `OPTIONS` preflight from `frontend_url` gets `access-control-allow-origin`.
- The MinIO `raw` bucket: bootstrap creates it with boto3 if missing.

`template/Makefile.jinja`:

```make
include .env
export

up:        ; docker compose up -d --build
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=100
env:       ; python3 scripts/make_env.py
bootstrap: ; cd scripts && uv run python bootstrap.py
brand:     ; cd scripts && uv run python brand.py
sync-plans:; docker compose exec -T backend uv run python -m app.billing.sync
migrate:   ; docker compose exec -T backend uv run alembic upgrade head
doctor:    ; cd scripts && uv run python doctor.py
check:
	cd backend && uv run ruff check . && uv run mypy && TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_test uv run pytest -q
	cd jobs && uv run ruff check . && uv run pytest -q
	cd scripts && uv run pytest -q
	cd frontend && npm run lint && npm run typecheck && npm test && npm run build
	cd .claude/hooks && python3 -m pytest -q
e2e:       ; cd e2e && npm ci && npx playwright install --with-deps chromium && npx playwright test
```

`template/scripts/make_env.py`: reads `.env.example`, copies to `.env` if absent, fills each blank key whose comment line above starts with `# Generate` using the shown `openssl` command via `subprocess`, leaves Stripe keys blank, and prints which keys still need a value.

`template/scripts/doctor.py`: connects to `app` Postgres and prints workspaces with `status = 'creating'` older than 5 minutes, subscriptions whose `updated_at` is older than 1 day while `pending`, and `webhook_events` with `processed_at IS NULL`; exit code 1 if any found. Test it in `scripts/tests/test_doctor.py` against SQLite with the same three tables (one row of each problem → exit 1; clean → exit 0).

`template/scripts/smoke_zitadel.py`: after bootstrap, uses the backend PAT to create a throwaway org, grant the project, add the admin human user as `member`, then deletes the org. Prints `OK` or the failing call. This checks the cross-org role grant against a real Zitadel before e2e.

- [ ] **Step 5: Run unit tests**

Run: `make dev && cd .dev/acme/scripts && uv run pytest -q`
Expected: all pass.

- [ ] **Step 6: Bring it up for real (manual check)**

In a generated product: `make env`, paste Stripe test keys into `.env`, `make up`, `make bootstrap`, `cd scripts && uv run python smoke_zitadel.py`.
Expected: `Ready: open http://<domain>:5173` and `OK`. Open the app, sign in through the branded Zitadel page.

- [ ] **Step 7: Commit**

```bash
git add template
git commit -m "feat: Docker Compose stack, idempotent bootstrap, env generator and doctor"
```

---

### Task 13: Agent rules, guard hook, isolation test, CI and the end-to-end test

**Files:**
- Create: `template/CLAUDE.md.jinja`, `template/.claude/settings.json`, `template/.claude/hooks/guard.py`, `template/.claude/hooks/test_guard.py`, `template/backend/tests/test_isolation.py`, `template/.github/workflows/backend.yml`, `frontend.yml`, `jobs.yml`, `e2e.yml`, `template/e2e/package.json`, `template/e2e/playwright.config.ts`, `template/e2e/signup-to-premium.spec.ts`, `.github/workflows/template.yml`, `tests/test_generated_checks.py`

**Interfaces:**
- Consumes: everything.
- Produces: `guard.py` reads the hook JSON on stdin and exits 2 (block) with a reason for: reading `.env` / `.bootstrap/*.pat`, any `sk_live_` string, `git push` to `main`, `git push --force`, `rm -rf` outside the repo. Exit 0 otherwise.

- [ ] **Step 1: Write the failing tests**

`template/.claude/hooks/test_guard.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).with_name("guard.py")


def run(tool: str, tool_input: dict[str, str]) -> int:
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, text=True, capture_output=True).returncode


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Read", {"file_path": "/repo/.env"}),
        ("Bash", {"command": "cat .env"}),
        ("Bash", {"command": "cat .bootstrap/backend.pat"}),
        ("Bash", {"command": "git push origin main"}),
        ("Bash", {"command": "git push --force origin feat/x"}),
        ("Bash", {"command": "echo sk_live_x"}),
        ("Write", {"file_path": "x.py", "content": "KEY='sk_live_x'"}),
    ],
)
def test_blocked(tool: str, tool_input: dict[str, str]) -> None:
    assert run(tool, tool_input) == 2


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Read", {"file_path": "/repo/.env.example"}),
        ("Bash", {"command": "git push -u origin feat/billing"}),
        ("Bash", {"command": "make check"}),
    ],
)
def test_allowed(tool: str, tool_input: dict[str, str]) -> None:
    assert run(tool, tool_input) == 0
```

`template/backend/tests/test_isolation.py` — architecture test that every route except an allow-list depends on `current_workspace` or `require_principal`, and that a principal for workspace A gets 403 or empty results for workspace B on every GET route:

```python
from fastapi.routing import APIRoute

from app.auth.deps import require_principal
from app.main import create_app
from app.workspaces.routes import current_workspace

PUBLIC = {"/health", "/billing/plans", "/billing/webhooks/lago"}


def _deps(route: APIRoute) -> set[object]:
    seen: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        d = stack.pop()
        seen.add(d.call)
        stack.extend(d.dependencies)
    return seen


def test_every_route_is_authenticated_or_public() -> None:
    for route in create_app().routes:
        if isinstance(route, APIRoute) and route.path not in PUBLIC and not route.path.startswith("/docs"):
            deps = _deps(route)
            assert require_principal in deps or current_workspace in deps, route.path


def test_workspace_header_cannot_reach_other_workspace(client, owner_headers, db_session) -> None:  # type: ignore[no-untyped-def]
    import uuid
    from app.workspaces.models import Workspace
    other = Workspace(name="Other", owner_user_id="u-other", zitadel_org_id="org-other", status="ready")
    db_session.add(other)
    db_session.flush()
    for path in ["/me/workspace", "/me/access", "/demo/premium-report"]:
        r = client.get(path, headers=owner_headers | {"X-Workspace-Id": str(other.id)})
        assert r.status_code == 403, path
    r = client.get("/me/workspace", headers=owner_headers | {"X-Workspace-Id": str(uuid.uuid4())})
    assert r.status_code == 403
```

(Import the `owner_headers` fixture from `tests.test_checkout` at the top of the file.)

`template/e2e/signup-to-premium.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

const APP = process.env.APP_URL!;

test("sign up → workspace → pay → premium report", async ({ page }) => {
  const email = `e2e+${Date.now()}@example.com`;
  await page.goto(APP);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: /register/i }).click();
  await page.getByLabel(/first name/i).fill("E2E");
  await page.getByLabel(/last name/i).fill("User");
  await page.getByLabel(/e-?mail/i).fill(email);
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByLabel(/^password$/i).fill("Correct-horse-battery-9");
  await page.getByLabel(/confirm password/i).fill("Correct-horse-battery-9");
  await page.getByRole("button", { name: /continue/i }).click();

  await page.getByLabel("Workspace name").fill("E2E Co");
  await page.getByRole("button", { name: "Create workspace" }).click();

  await page.getByRole("button", { name: "Choose Starter" }).click();
  await page.waitForURL(/checkout\.stripe\.com/);
  await page.getByLabel(/card number/i).fill("4242 4242 4242 4242");
  await page.getByLabel(/expiration/i).fill("12 / 34");
  await page.getByLabel(/cvc/i).fill("123");
  await page.getByRole("button", { name: /save|subscribe|pay/i }).click();

  await page.waitForURL(`${APP}/billing/return`);
  await expect(page.getByRole("link", { name: "Open premium report" })).toBeVisible({ timeout: 90_000 });
  await page.getByRole("link", { name: "Open premium report" }).click();
  await expect(page.getByText("Generated for E2E Co")).toBeVisible();
});
```

Zitadel's registration labels and Stripe's hosted checkout labels are owned upstream; if a selector fails, update the locator in this one file (record the upstream version in a comment).

`tests/test_generated_checks.py` (template repo): runs `make check` in the generated product with `subprocess.run(["make", "check"], cwd=product_dir, check=True)`; marked `@pytest.mark.slow` and selected in CI.

- [ ] **Step 2: Run to verify failure**

Run: `make dev && cd .dev/acme/.claude/hooks && python3 -m pytest -q`
Expected: FAIL — `guard.py` missing.

- [ ] **Step 3: Implement the guard, CLAUDE.md, settings and workflows**

`template/.claude/hooks/guard.py`:

```python
import json
import re
import sys

BLOCKS = [
    (re.compile(r"(^|[\s/])\.env(\s|$)"), "reading .env is not allowed"),
    (re.compile(r"\.bootstrap/[^\s]*\.pat"), "reading bootstrap tokens is not allowed"),
    (re.compile(r"sk_live_[0-9A-Za-z]+"), "live Stripe keys are not allowed"),
    (re.compile(r"git\s+push\b.*\b(main|master)\b"), "pushing to main is not allowed"),
    (re.compile(r"git\s+push\b.*(--force|-f\b|\+)"), "force pushes are not allowed"),
]


def main() -> int:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input", {})
    text = " ".join(str(v) for v in tool_input.values())
    for pattern, reason in BLOCKS:
        if pattern.search(text):
            print(reason, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`template/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|Read|Write|Edit", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/guard.py" }] }
    ]
  },
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.bootstrap/**)"]
  }
}
```

`template/CLAUDE.md.jinja`:

```markdown
# {{ product_name }}

Generated from prodij/copio. Layout: `frontend/` `backend/` `jobs/` `infra/` `brand/`.

## Loop
1. Branch `feat/<topic>`. 2. Change + tests. 3. `make check`. 4. For UI or billing changes, `make up && make e2e`.
5. Commit, push your branch, open a PR. Never push to `main`.

## Rules
- Access is checked only with `require_feature` (backend/app/access/deps.py). Plans change only in backend/app/billing/plans.yaml, then `make sync-plans`.
- The backend is the only caller of Zitadel and Lago. The frontend calls only the backend, through `src/api/client.ts` (raw `fetch` is a lint error).
- Every product table has `workspace_id`; jobs use `ScopedDb`.
- Missing data shows "Unavailable", never 0.
- Never read `.env` or `.bootstrap/`; never use live Stripe keys. The guard hook blocks these.
- Business logic comes from intent notes in ~/brain; write it fresh, never port code.
```

Workflows: `backend.yml` (on `pull_request` paths `backend/**`; Postgres 15 service; `uv sync`, ruff, mypy, pytest), `jobs.yml` (paths `jobs/**`), `frontend.yml` (paths `frontend/**`, `backend/openapi.json`; `npm ci`, lint, typecheck, test, build; also fails if `npm run gen:api` changes `schema.d.ts`), `e2e.yml` (nightly `schedule: cron "0 7 * * *"` and `workflow_dispatch`; needs repo secrets `STRIPE_SECRET_KEY`, `STRIPE_API_KEY` set by the human; runs `make env`, `make up`, `make bootstrap`, `make e2e`). Pin every action to a full commit SHA with a `# vX.Y.Z` comment.

`.github/workflows/template.yml` (template repo): on PR and push to `main`: `uv run pytest -q` (fast tests), then `uv run pytest -q -m slow` (generates a product and runs its `make check` with a Postgres service), then, on `workflow_dispatch` or nightly, the generated product's e2e with the Stripe test secrets.

- [ ] **Step 4: Run all checks**

Run: `uv run pytest -q && uv run pytest -q -m slow`
Expected: all pass, including the generated product's `make check`.

- [ ] **Step 5: Run the end-to-end test**

In a generated product with real Stripe test keys: `make env && make up && make bootstrap && make e2e`
Expected: `1 passed`. This is milestone 1's definition of done (spec §1).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: agent guardrails, isolation test, path-filtered CI and the sign-up-to-premium e2e"
```

---

## Done when

- `uv run pytest -q -m slow` passes in the template repo (generated product: lint, typecheck, all unit tests).
- In a freshly generated product, `make env && make up && make bootstrap && make e2e` passes with Stripe test keys.
- The human has pushed tag `v1-diagnostic-archive` and reviewed the PR from `feat/boilerplate-m1` into `main`.
