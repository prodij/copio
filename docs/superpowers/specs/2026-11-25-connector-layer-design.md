# Connector layer: design and parallel build

Date: 2026-11-25. Decided by J on 2026-11-24: the layer lives in the template's `main`, so every
generated product gets it. Research and reasons: `~/brain/Projects/Copio/Connector orchestration
research - 2026-11-24.md`. Phases: `~/brain/Projects/Copio/Connector layer - build plan 2026-11-24.md`.

## What the layer does

A product connects external accounts and keeps their data in sync in a way that recovers from failure
and tells the truth about what is complete.

```
schedules / webhooks / manual ──► sync_runs row (outbox) ──► dispatcher ──► Procrastinate queue
                                                                              │ (run id only)
                                                                              ▼
           credentials (encrypted) ──► runner ◄──► provider API      bounded workers
                                         │
                       raw object (S3) ──┤ save_raw (backlog)
                                         ▼
                 ledger.publish (fenced, newer version wins) ──► synced_records
                                         ▼
                 ledger.complete ──► sync_streams.covered_to advances only when the backlog is empty
```

## Fixed rules (every session)

1. **Contract first.** `template/jobs/jobs/sync/contract.py` and migration `0004_connector_layer.py`
   are the shared contract. Only the integrator edits them, along with `backend/app/connectors/models.py`,
   `backend/app/audit/` and `jobs/tests/conftest.py`. If you need a change, make the smallest local
   workaround and list the change you need in your final report.
2. **The queue carries run ids only.** Never a token, credential, or raw payload in a queue job, a log
   line, an exception message, an API response, or `error_detail`.
3. **Fences.** Every write after `claim` carries the lease. A write with an old fence raises
   `StaleLease` and writes nothing.
4. **Raw first.** A page's raw bytes are stored and recorded (`save_raw`) before parsing. A run is not
   complete while any of its raw objects is unprocessed.
5. **Versions.** `Record.version` strings sort lexicographically in version order (ISO-8601 UTC
   timestamps, or zero-padded integers). Publishing never replaces a newer version with an older one.
6. **Deletions** are inferred only from a complete snapshot (`Page.complete_snapshot` /
   `complete(snapshot_complete=True)`). Never from a truncated or failed fetch.
7. **Reports** are requested once per run. The report id lives in the run checkpoint. Retries poll or
   download; they never request again. `cancelled_no_data` is a successful, empty result.
8. **Outbox.** Anything that wants work done inserts a `sync_runs` row with `status='queued'` and
   `enqueued_at` null, in its own transaction. Only the dispatcher (S2) talks to the queue.
9. **Audit.** Every operator action and connection change calls `app.audit.record` in the same
   transaction (backend), or inserts into `audit_events` with `actor_type='system'` (jobs).
10. **Synthetic only.** No real provider accounts, credentials, NG data or network calls. Tests that
    need HTTP use `respx`. Never copy code from NG or Skylit repositories.
11. **Template rules.** `CLAUDE.md` at the repo root applies: `uv run pytest -q` at the root before
    every commit, `copier copy` needs `--trust`, ruff and mypy strict must pass in the generated product.

## Testing

- Each session runs its own Postgres 15 on its own port, so sessions never share a database:
  `docker run -d --rm --name copio-<session>-pg -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app
  -e POSTGRES_DB=app_test -p 127.0.0.1:<port>:5432 postgres:15`, then
  `export TEST_DATABASE_URL=postgresql+psycopg://app:app@127.0.0.1:<port>/app_test`.
  Ports: S1 55431, S2 55432, S3 55433, S4 55434, S5 55435. Stop your container when done.
- Jobs tests that need a database take the `pg_engine` / `clean_tables` / `two_workspaces` fixtures
  from `jobs/tests/conftest.py`. These build the schema from the real migrations.
- Fast loop: `make dev` at the repo root generates `.dev/acme`. Work in `template/`, regenerate, and run
  `make check` in `.dev/acme`, or run `uv run pytest` inside `.dev/acme/jobs` or `.dev/acme/backend`.
  Before you finish, run `uv run pytest -q` at the repo root (it includes the slow generated-product checks).

## Work split: who owns which files

Writers never touch another session's files. The places that will collide on merge (`backend/app/main.py`
router includes, `backend/openapi.json`, `frontend/src/api/schema.d.ts`, lock files) are resolved by
the integrator with `make regen`. Don't spend time keeping them in sync with other sessions.

| Session | Owns | Builds |
|---|---|---|
| **S1 Ledger** | `jobs/jobs/sync/ledger.py`, `jobs/tests/test_ledger.py` | `PgLedger`, implementing the `Ledger` protocol on the 0004 tables: idempotent `create_run` by dedupe key; `claim` with `select … for update` on `sync_streams`, refusing a live lease and bumping `fence` on takeover; heartbeat; fenced checkpoint, save_raw, publish and complete; newer-version-wins upsert into `synced_records` in the same transaction as marking the raw object processed; contiguous coverage advance only when the run's backlog is empty; deletion inference only for complete snapshots; attempt counting, wait and fail. Port the stage, verify and atomic-publish ideas and receipts from `prodij/copio-operations` (`jobs.py`, `durability.py`), on Postgres. |
| **S2 Engine** | `jobs/jobs/sync/engine.py`, `dispatcher.py`, `scheduler.py`, `budgets.py`, `retry.py`, `jobs/jobs/worker.py`, `jobs/tests/test_engine*.py`, `test_scheduler_sync.py`, `test_budgets.py`, a new migration `s2_procrastinate` (Procrastinate's schema), `jobs/Dockerfile`, the `jobs` service in `docker-compose*.jinja`, and retiring `jobs/jobs/scheduler.py` | `ProcrastinateEngine` (Procrastinate 3.11, Postgres connector). The dispatcher moves outbox rows into the queue (`enqueued_at`, `queue_job_id`) and is safe to run twice. Dynamic per-connection schedules from `sync_schedules`: timezone-aware cron, jitter, overlap policy (skip or queue_one), a catch-up window, and paused connections or schedules creating nothing. Separate `sync` and `backfill` queues, and a per-stream Procrastinate lock so a backfill cannot starve incremental work. Token-bucket `rate_budgets` keyed by provider quota scope, honoring `blocked_until`. A retry policy with exponential backoff, full jitter, a Retry-After floor and bounded attempts. Stalled-job recovery (Procrastinate's `retry_stalled_jobs` as a periodic task). `billing_reconcile` and `sample_fetch` keep running as periodic tasks. |
| **S3 Vault** | `backend/app/connectors/vault.py`, `backend/app/connectors/routes.py` (connection CRUD and state), `backend/tests/test_connections*.py`, `backend/tests/test_vault.py`, `jobs/jobs/sync/credentials.py`, `jobs/tests/test_credentials.py`, KMS additions in `infra/` (a new `kms.tf` plus IAM; load the `terraform-iac` skill first) | Envelope encryption (AES-256-GCM via `cryptography`). The data key is wrapped by AWS KMS when `CONNECTOR_KMS_KEY_ID` is set, and otherwise by a local key-encryption key from `CONNECTOR_LOCAL_KEK` (dev and test only; refuse to start with it when `APP_ENV=production`). One ciphertext format shared by backend and jobs, proven by a test vector both sides decrypt. `PgCredentialStore`: `get`, `rotate` (version-checked, refresh serialized with `pg_advisory_xact_lock` per connection, returns the newer credential if it lost the race), `mark_revoked` (sets the connection to `reconnect_needed`). REST, all workspace-scoped: list, create (synthetic provider only, credentials write-only), pause, resume, reconnect (replaces credentials, back to healthy), disconnect, and per-dataset schedule upsert. Every route writes an audit event. No response ever contains a credential. |
| **S4 Runner and contract** | `jobs/jobs/sync/runner.py`, `jobs/jobs/sync/testing/` (synthetic providers), `jobs/tests/contract/**`, `jobs/tests/test_runner.py` | `execute(run_id, deps)`: claim, then fetch (incremental pages / report lifecycle / replay from raw), store raw via `RawStore`, save_raw, publish, checkpoint, complete. Maps `RateLimited` to wait plus a budget block, `TransientError` to a retry, `AuthRevoked` to `mark_revoked`, and `PermanentError` to a bounded fail. Heartbeats on long pages. Synthetic providers with fault injection: a paginated incremental feed, and an async report (queued, processing, done, cancelled_no_data, fatal). **The ten contract scenarios** (below), parametrized over implementations. Develop against in-memory fakes of `Ledger`, `CredentialStore` and `Engine` in `jobs/tests/contract/fakes.py` (they are also an executable spec of the semantics); the integrator adds the Postgres parametrization at merge. Write the pass thresholds in `jobs/tests/contract/thresholds.py` before the first run. |
| **S5 Management** | `backend/app/connectors/health.py`, `backend/app/connectors/runs_routes.py`, `backend/tests/test_runs_routes.py`, `backend/tests/test_health_routes.py`, `frontend/src/pages/Connections*.tsx`, `frontend/src/pages/ConnectionDetail*.tsx`, `frontend/src/components/sync/**`, the router entries for those pages | Read routes: dataset health per connection (last complete publication separate from last attempt, coverage, missing periods, lag against the freshness target, replay backlog), and run list and detail (stage, attempts, sanitized error, request ref, record counts). Action routes that write outbox rows and audit events: refresh now (manual, shares normal limits), retry a failed run, resume a waiting run, replay stored raw. Operator health: queue age, oldest unpublished coverage, 429 count, expired leases, auth failures, failed runs needing action. Frontend pages for Connections and Connection detail using the existing UI components, wired to the generated API client. A green run status must never hide a stale dataset. |

## The ten contract scenarios (S4 writes them; everything must pass them)

| # | Fault | Must observe |
|---|---|---|
| 1 | Duplicate timer or webhook; restart after records are written | One logical record per key and version; duplicate attempts visible on the run |
| 2 | Worker killed after save_raw, before publish | Recovery publishes or fails boundedly; coverage never advances past unpublished raw |
| 3 | Two workers claim one stream | Only the current fence publishes; the stale worker gets StaleLease and writes nothing |
| 4 | 429, timeout, 5xx | Bounded retries with provider-aware delay and jitter; no busy loop |
| 5 | Revoked token; refresh race | Connection becomes reconnect_needed; one rotation wins; nothing overwritten |
| 6 | Large backfill next to a small incremental | The incremental finishes within the threshold's budget |
| 7 | Report pending → done / no data / fatal | Resumes from the saved stage; never re-requested; terminal states distinct |
| 8 | Stale poll after a newer webhook | No stale overwrite |
| 9 | Schema change, missing page, partial snapshot | Coverage not advanced; no false completion; no mass deletion |
| 10 | Pause, resume, replay | Bounded behavior, connector version traced, audit event written |

## Integration (the integrator, in the orchestrating session)

Merge order: S1, S3, S2, S4, S5. After each merge, linearize the session migrations after 0004, run
`make regen`, add the Postgres parametrization to the contract suite once S1 is in, and run the full
`uv run pytest -q` at the repo root with Postgres. The phase is done when all ten scenarios pass on
Postgres in CI and a freshly generated product runs one synthetic sync end to end.
