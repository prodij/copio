"""One synthetic sync through every real piece: a schedule row, the scheduler tick, the dispatcher, a
Procrastinate worker, and the runner the worker loads by default (`build_executor`, built from the
environment), on Postgres and moto S3. Then an operator replay, for the audit trail."""

import base64
import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import Engine, text

from jobs.sync.contract import RunStatus
from jobs.sync.credentials import LocalKeyWrapper, Secret, Vault
from jobs.sync.dispatcher import Dispatcher
from jobs.sync.engine import ProcrastinateEngine
from jobs.sync.ledger import PgLedger
from jobs.sync.runner import build_executor, register_provider, unregister_provider
from jobs.sync.scheduler import Scheduler
from jobs.sync.testing import SyntheticFeed, SyntheticWorld

BUCKET = "e2e-raw"
TOKEN = "tok-e2e"  # noqa: S105 - synthetic, not a secret
PROVIDER = "synthetic-feed"


@pytest.fixture
def db(clean_tables: Engine) -> Iterator[Engine]:
    yield clean_tables
    with clean_tables.begin() as conn:
        conn.execute(text("truncate procrastinate_jobs, procrastinate_events, procrastinate_periodic_defers,"
                          " procrastinate_workers cascade"))


@pytest.fixture
def s3() -> Iterator[object]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_a_scheduled_sync_end_to_end(db: Engine, pg_url: str, two_workspaces: tuple[str, str], s3: object,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    kek = os.urandom(32)
    for name, value in {"DATABASE_URL": pg_url, "RAW_BUCKET": BUCKET, "AWS_DEFAULT_REGION": "us-east-1",
                        "CONNECTOR_LOCAL_KEK": base64.b64encode(kek).decode()}.items():
        monkeypatch.setenv(name, value)
    for name in ("S3_ENDPOINT_URL", "APP_ENV", "CONNECTOR_KMS_KEY_ID", "SYNC_PROVIDERS"):
        monkeypatch.delenv(name, raising=False)

    # A connected synthetic account with an encrypted credential and an hourly schedule.
    workspace_id = uuid.UUID(two_workspaces[0])
    connection_id = uuid.uuid4()
    with db.begin() as conn:
        conn.execute(text(
            "insert into connections (id, workspace_id, provider, account_ref, display_name)"
            " values (:id, :ws, :provider, 'acct-e2e', 'Synthetic e2e')"),
            {"id": connection_id, "ws": workspace_id, "provider": PROVIDER})
        vault = Vault(LocalKeyWrapper(kek))
        blob = vault.seal(connection_id, Secret(access_token=TOKEN, extra={}))
        conn.execute(text("insert into credentials (connection_id, ciphertext, key_id) values (:id, :b, :k)"),
                     {"id": connection_id, "b": blob, "k": vault.key_id})
        conn.execute(text("insert into sync_schedules (connection_id, dataset, kind, cron)"
                          " values (:id, 'events', 'incremental', '0 * * * *')"), {"id": connection_id})

    world = SyntheticWorld()
    world.grant(connection_id, TOKEN)
    feed = SyntheticFeed(world)
    register_provider(PROVIDER, lambda spec: feed)
    try:
        # Scheduler → outbox row.
        tick = Scheduler(db, connector_version=lambda provider: feed.version).tick(datetime.now(UTC))
        [run_id] = tick.created

        # Dispatcher → Procrastinate job carrying the run id only.
        engine = ProcrastinateEngine(pg_url, executor=build_executor(), db=db)
        assert Dispatcher(engine).drain() == 1
        with db.connect() as conn:
            [args] = conn.execute(text("select args from procrastinate_jobs")).scalars().all()
        assert args == {"run_id": str(run_id)}

        # Worker → runner → ledger.
        engine.run_worker(queues=["sync", "backfill"], until_idle=True)

        ledger = PgLedger(db)
        run = ledger.get_run(run_id)
        assert run is not None and run.status is RunStatus.SUCCEEDED
        assert feed.call_count == 1
        with db.connect() as conn:
            records = conn.execute(text(
                "select record_key, workspace_id, run_id from synced_records where connection_id = :c"),
                {"c": connection_id}).all()
            stream = conn.execute(text(
                "select covered_from, covered_to, last_publish_run_id from sync_streams"
                " where connection_id = :c and dataset = 'events'"), {"c": connection_id}).one()
            raw = conn.execute(text("select storage_key, processed_at from raw_objects where run_id = :r"),
                               {"r": run_id}).all()
        assert len(records) == 3 and {r.workspace_id for r in records} == {workspace_id}
        assert (stream.covered_from, stream.covered_to) == (run.spec.window.start, run.spec.window.end)
        assert stream.last_publish_run_id == run_id
        assert len(raw) == 1 and raw[0].processed_at is not None
        assert s3.get_object(Bucket=BUCKET, Key=raw[0].storage_key)["Body"].read()  # type: ignore[attr-defined]
        assert ledger.verify_run(run_id)["coverage_advanced"] is True

        # Operator replay → outbox → queue → runner, leaving a system audit event.
        replay_id = ledger.create_replay(run_id, feed.version, requested_by="user-1")
        assert Dispatcher(engine).drain() == 1
        engine.run_worker(queues=["sync", "backfill"], until_idle=True)
        replay = ledger.get_run(replay_id)
        assert replay is not None and replay.status is RunStatus.SUCCEEDED
        assert feed.call_count == 1  # replay never called the provider
        with db.connect() as conn:
            events = conn.execute(text(
                "select workspace_id, actor_type, action, target_id, detail from audit_events")).all()
        [event] = [e for e in events if e.action == "run.replay"]
        assert (event.workspace_id, event.actor_type, event.target_id) == (workspace_id, "system",
                                                                           str(replay_id))
        detail = event.detail if isinstance(event.detail, dict) else json.loads(event.detail)
        assert detail["replay_of"] == str(run_id) and detail["coverage_advanced"] is True
        assert TOKEN not in json.dumps([dict(e._mapping) for e in events], default=str)
    finally:
        unregister_provider(PROVIDER)
