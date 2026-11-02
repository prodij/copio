# Copio boilerplate, milestone 1 (local) — design

- **Date:** 2026-10-30
- **Status:** draft for review
- **Owner:** James (personal project; separate from NG and Skylit)
- **Diagrams:** [2026-10-30-copio-system-design.html](2026-10-30-copio-system-design.html)

## 1. Goal

Turn `prodij/copio` into a **Copier template** that generates a standalone SaaS product with customer sign-in, workspaces, subscription billing and plan-based feature access already working.

Milestone 1 is done when, in a freshly generated product running on Docker Compose, a person can:

1. sign up through the product's branded Zitadel login,
2. create a workspace,
3. choose the starter plan and pay with Stripe's test card `4242 4242 4242 4242`,
4. see a sample `premium_report` feature switch on, driven by the Lago webhook, not by the browser returning from Stripe.

`make e2e` proves this with one Playwright test. Stripe is optional (note 2026-11-01): without a key steps 1 and 2 still work, step 3 says billing isn't set up, and the payment test is reported as skipped.

## 2. The pattern this serves

Products are built in three steps, repeated per product:

1. **Boilerplate**: generate the product from this template (`copier copy --trust`).
2. **Extract intent**: read an existing system (code, plans, tests) and write what it must do and why into `~/brain` as notes that don't depend on any language or framework: rules, formulas, edge cases, worked examples.
3. **Apply**: implement the business logic fresh in the generated product from those notes, using the stack's own idioms. Generic fixes found while building a product flow back into the template; `copier update --trust` brings them to existing products.

The first product through the pattern is the **Copio diagnostic agent**, rebuilt (see §12).

## 3. Decisions

| # | Decision | Rejected alternatives and why |
|---|---|---|
| D1 | Each product stands alone: one repo, later one AWS account, no shared runtime platform | Shared platform (one Zitadel, one Lago, a platform API): pays off only with several live products; heavy from day one |
| D2 | One repo per product with `frontend/` `backend/` `jobs/` `infra/` | Three repos per product: three PRs per cross-cutting change, a copied API contract, three CI setups |
| D3 | Each folder is checked, and from milestone 2 deployed, on its own by path-filtered CI | Deploying everything on every push |
| D4 | Customer sign-in: Zitadel, one instance per product | Cognito pool: weak branding. Own login code: riskiest code to hand to agents |
| D5 | Billing: Lago, run unmodified; payments by Stripe | Closed-source billing SaaS: user wants open source. Forking Lago: upgrade and AGPL burden |
| D6 | Pricing: designed for tier + usage; launch with one flat plan | — |
| D7 | Scheduled work in `jobs/`: Lambda-shaped handlers, raw data to S3 first | Worker container: drops S3-first replay. Separate cron repo: couples products |
| D8 | Products are created with Copier and can pull template updates | GitHub template repo: one-time copy, fixes don't propagate |
| D9 | Brand tokens set at creation feed the app theme, Zitadel and Lago | Fixed default look; per-product hand styling |
| D10 | Milestone 1 runs locally on Docker Compose; AWS is milestone 2 | AWS from day one: account setup blocks progress, slower debugging |
| D11 | Stack: React + Vite + TypeScript, shadcn/ui on Base UI, Tailwind; FastAPI, SQLAlchemy, Alembic, Postgres; Python jobs | — |
| D12 | Same stack choices as NG's projects, but **no code is copied from NG or Skylit repos**; everything is written fresh | Copying ng-frontend / ng-backend files: they belong to NG |

## 4. Repository layout

### 4.1 The template repo (`prodij/copio`)

```
copier.yml                 questions (§4.3) and post-generation tasks
template/                  everything that becomes a product (Jinja-templated where needed)
tests/                     template self-test: generate → lint → typecheck → unit → e2e
docs/superpowers/specs/    this spec and later ones
CLAUDE.md                  rules for agents working on the template itself
```

Before the template lands, the current Copio code is tagged `v1-diagnostic-archive` (a few minutes' work, done first) and then removed from `main`. Piece 0 (§12) reads the code from that tag, so the removal doesn't block it.

### 4.2 A generated product

```
frontend/          React + Vite + TS, shadcn/ui (Base UI), Tailwind, typed API client
backend/           FastAPI app; modules auth, workspaces, billing, access; Alembic migrations
jobs/              handlers, schedules.yaml, local scheduler, sample job
infra/             placeholder README in milestone 1
brand/             brand.yaml + logo.svg; `make brand` generates tokens
docker-compose.yml all local services (§8)
Makefile           up · bootstrap · brand · sync-plans · check · e2e · doctor
.env.example       every variable, no values; .env is git-ignored
.github/workflows/ path-filtered: frontend, backend, jobs
CLAUDE.md, .claude/ agent rules, settings and guard hook (§10)
```

### 4.3 Copier questions

`product_name`, `product_slug`, `domain` (placeholder, e.g. `copio-agent.localhost`), `brand_primary`, `brand_accent`, `brand_font`, `logo_path`, `starter_plan_price_usd`, `starter_plan_interval` (`month` | `year`).

## 5. Sign-in and workspaces

- Each product runs its own Zitadel instance with one **project** for the product and one **app client** (OIDC, authorization code + PKCE) for the frontend.
- A **customer workspace is a Zitadel organization.** Roles on the product project: `owner`, `member`.
- The frontend signs in with `oidc-client-ts`. The backend validates every request's access token against Zitadel's JWKS and reads the organization ID and role claims into a `Principal(user_id, workspace_id, role)`.
- `POST /workspaces {name}` (any signed-in user without a workspace):
  1. insert a `workspaces` row with `status = creating`,
  2. create the Zitadel organization through a service account, make the caller its owner, record `zitadel_org_id`,
  3. create the Lago customer (`external_id = workspace.id`, Stripe as payment provider when a key is configured), record `lago_customer_id`,
  4. set `status = ready`.

  Each step is recorded, so a retry resumes from the last finished step and never creates duplicates.
- Invites and member lists stay in Zitadel (its own invite emails). The backend stores no member list.

## 6. Billing and access

- **Plans are code:** `backend/billing/plans.yaml` holds per plan the code, name, price, interval and features (booleans and limits, e.g. `premium_report: true`, `seats: 5`). `make sync-plans` creates or updates them in Lago. Milestone 1 ships one plan, `starter`.
- **Checkout:** `POST /billing/checkout {plan_code}` (owner only) creates the Lago subscription for the workspace and returns the Stripe-hosted checkout URL that Lago provides for collecting the payment method. The frontend redirects there. Coming back from Stripe changes nothing by itself. Without a Stripe key it answers `501` with a message saying billing isn't set up, and writes nothing. A Lago customer created before the key gets the Stripe provider at its first checkout (Lago's upsert on `external_id`).
- **Webhooks:** `POST /billing/webhooks/lago` verifies Lago's webhook signature, inserts the event into `webhook_events` (unique on Lago's event ID; a duplicate is acknowledged and ignored), then updates `subscriptions`.
- **States:** `pending` → `active` (invoice paid) → `past_due` (payment failed; Stripe retries) → `active` (retry paid) or `canceled` (retries exhausted or canceled at period end).
- **Access:** `require_feature(name)` is a FastAPI dependency. It allows the request when the workspace's subscription is `active` or `past_due` and its plan grants the feature; otherwise it returns `402` with the reason. It is the only access check. `GET /me/access` returns plan, state, features and `billing_configured` so the frontend can show or hide UI; the backend re-checks on every request.
- **Usage, ready but unpriced:** `billing.record_usage(workspace_id, metric, value)` sends events to Lago. One sample metric (`reports_generated`) is recorded, with no price attached.
- **Reconcile:** a job (§7) asks Lago for each workspace's current subscription every 15 minutes and repairs any state that differs. Webhooks make changes fast; reconcile keeps them correct.

### 6.1 Backend tables (the shell's only tables)

| Table | Columns |
|---|---|
| `workspaces` | `id` (uuid), `name`, `zitadel_org_id`, `lago_customer_id`, `status` (`creating`, `ready`), `created_at` |
| `subscriptions` | `workspace_id`, `plan_code`, `state`, `lago_subscription_id`, `current_period_end`, `updated_at` |
| `webhook_events` | `id` (Lago's event ID), `type`, `received_at`, `payload` (jsonb), `processed_at` |

Products add their own tables. Every product table carries `workspace_id`.

## 7. Jobs

- A job is a Python function `handler(event, context)`, so the same code runs as a Lambda in milestone 2.
- **Raw first:** a job that fetches outside data writes the raw response to object storage at `raw/<source>/<workspace_id>/<yyyy>/<mm>/<dd>/<run_id>.<ext>` before parsing. A processor turns raw objects into rows, and can be re-run from storage after a parsing fix.
- **Workspace scope:** jobs receive `workspace_id`; the jobs database helper refuses a query without one.
- `jobs/schedules.yaml` lists job and cron expression. Locally, a scheduler container runs them. In milestone 2 the same file becomes EventBridge schedules.
- Milestone 1 jobs: `sample_fetch` (public JSON feed → raw → one row) and `billing_reconcile` (§6).

## 8. Branding and local running

- `brand/brand.yaml`: name, logo (SVG), primary and accent colors, neutrals, font, each for light and dark.
- `make brand` generates:
  - `frontend/src/brand.css`: CSS variables for the shadcn/Tailwind theme, light and dark,
  - the Zitadel label policy (colors, logo, font), applied through Zitadel's API,
  - Lago's organization name and logo, used on invoices.
- `make up` starts Docker Compose:
  - Postgres (databases `app`, `zitadel`, `lago`), Redis and SeaweedFS (S3; replaced MinIO, whose pinned image can no longer be pulled — note 2026-11-01),
  - Zitadel and its login UI,
  - Lago (api, worker, clock, front, pdf),
  - the backend, the frontend dev server and the job scheduler,
  - `stripe listen`, forwarding Stripe test webhooks to Lago (idle without a key).
- `make bootstrap` (once per machine):
  - creates the Zitadel project, app client and service account,
  - connects Lago to the Stripe test key from `.env`; with no key it says Stripe was skipped and how to add it, and finishes,
  - runs `sync-plans` and `brand`.
- Image versions for Zitadel, Lago and other services are pinned in `docker-compose.yml`.
- **Secrets:** `.env` is git-ignored and `.env.example` lists every variable without values. `prodij/copio` is public, so the template self-test fails if anything resembling a key is committed.

## 9. Failure handling

| Situation | Behaviour |
|---|---|
| Zitadel or Lago unreachable | `503` naming the dependency; nothing is reported as created |
| Workspace creation interrupted | Resumes from the recorded step on retry; `make doctor` lists workspaces stuck in `creating` |
| Webhook with a bad signature or unknown type | `400`, logged, no state change |
| Duplicate webhook | Acknowledged, ignored |
| Webhook missed or late | Fixed by `billing_reconcile` within 15 minutes |
| No Stripe key | Checkout `501` with a clear message, nothing written; `require_feature` still answers `402`; adding the key and re-running `make bootstrap` enables checkout, also for existing workspaces |
| Frontend loading / error / missing value | Skeleton / HTTP status with the API's message / "Unavailable", never `0` |

## 10. Testing and rules for agents

### Testing

- **Backend:** pytest. Zitadel and Lago are faked at the HTTP boundary with recorded responses. Contract tests check the webhook parser against Lago's documented payloads.
- **Access:** a table-driven test of every state × plan × feature combination.
- **Isolation:** an architecture test reads another workspace's data through every endpoint and job helper and must fail.
- **Frontend:** Vitest and Testing Library with a mocked API.
- **End to end:** `make e2e`, Playwright against real containers and Stripe test mode (the payment test is skipped without a key). Runs in the template self-test and nightly.
- **Template self-test (CI):** `copier copy --trust` into a temp dir, then lint, typecheck, unit tests, and e2e on the generated product.

### Agent rules (in each product's `CLAUDE.md` and `.claude/`)

- Agents own a change end to end: branch, tests, `make check`, PR.
- Agents never read `.env` or other secrets, never use live Stripe keys, and never push to `main`. A guard hook enforces this and has its own test.
- Plans change only in `plans.yaml`. Access is checked only through `require_feature`. Outside services are called only through typed clients. A lint rule blocks raw `fetch` in the frontend.

## 11. Out of scope for milestone 1

| Item | When |
|---|---|
| AWS infrastructure (Terraform, DNS, certificates) | Milestone 2, in a personal AWS account |
| Passkeys, social login | Once the product's real domain is chosen |
| Sales tax beyond Lago's built-in rates | Before taking real payments |
| Team and seat management screens | When a product needs per-seat pricing or custom roles |
| Usage-based prices | When a product defines them in `plans.yaml` |
| The Copio agent's own features | Piece 3 |

## 12. The surrounding pieces

| # | Piece | Depends on |
|---|---|---|
| 0 | Tag current Copio code `v1-diagnostic-archive`; extract its intent into `~/brain` (voice rules, citation rules, eval rig, Amazon diagnostics, pricing) | — |
| 1 | **This spec** | — |
| 2 | Milestone 2: `infra/` Terraform for a personal AWS account | 1 |
| 3 | Copio diagnostic agent, generated from the template, implemented from piece 0's notes, in its own repo | 0, 1 |

Pieces 0 and 1 can run in parallel.

## 13. To verify while planning

These are facts about upstream tools to check against their current docs, not open design choices:

- Lago: the endpoint that returns the Stripe checkout URL for a customer, the webhook signature scheme, and the event names for paid and failed invoices and subscription changes.
- Zitadel: the token claims that carry the organization ID and project roles, the current login UI image, and the label-policy API used for branding.
- Pinned versions of Zitadel, Lago and the Stripe CLI at planning time.
- The product repo name for piece 3 (proposed: `prodij/copio-agent`).
