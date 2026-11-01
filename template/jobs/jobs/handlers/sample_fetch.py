"""Sample job: fetch a public JSON feed, keep the raw response, turn it into one row per workspace.

Raw first (spec §7): the response is written to object storage before anything parses it, and
`process` builds the row from the stored object. After a parsing fix, re-run it from storage with
the event `{"reprocess": ["raw/fx/<workspace_id>/...", ...]}`.
"""

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import httpx
from botocore.config import Config
from sqlalchemy import create_engine

from jobs.db import ScopedDb
from jobs.storage import RawStore

FEED = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR"
SOURCE = "fx"


def parse(raw: bytes) -> str:
    """The USD→EUR rate from Frankfurter's `{"base": "USD", "rates": {"EUR": 0.9}}`."""
    return str(json.loads(raw)["rates"]["EUR"])


def workspace_of(key: str) -> str:
    """The workspace a raw key belongs to (`raw/<source>/<workspace_id>/...`)."""
    parts = key.split("/")
    if len(parts) < 7 or parts[0] != "raw" or parts[1] != SOURCE or not parts[2]:
        raise ValueError(f"not a raw {SOURCE} key: {key}")
    return parts[2]


def process(db: ScopedDb, store: RawStore, workspace_id: str, key: str) -> None:
    """Raw object → row. Upserts by raw_key, so a re-run replaces the value instead of adding a row."""
    if workspace_of(key) != workspace_id:
        raise ValueError(f"{key} does not belong to workspace {workspace_id}")
    db.execute(
        "insert into sample_rows (workspace_id, raw_key, value) values (:workspace_id, :raw_key, :value)"
        " on conflict (raw_key) do update set value = excluded.value",
        {"workspace_id": workspace_id, "raw_key": key, "value": parse(store.get(key))},
    )


def s3_client() -> Any:
    """AWS S3, or a local S3 server at S3_ENDPOINT_URL (SeaweedFS in Compose), addressed path-style
    (`http://host/bucket/key`) since a bucket subdomain does not resolve locally."""
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    config = Config(s3={"addressing_style": "path"}) if endpoint else None
    return boto3.client("s3", endpoint_url=endpoint, config=config)


def handler(event: dict[str, Any], context: object | None) -> dict[str, Any]:
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        db = ScopedDb(engine)
        s3 = s3_client()
        store = RawStore(os.environ["RAW_BUCKET"], s3)
        if keys := event.get("reprocess"):
            for key in keys:
                process(db, store, workspace_of(key), key)
            return {"reprocessed": len(keys)}
        run_id = uuid.uuid4().hex
        response = httpx.get(FEED, timeout=10.0)
        response.raise_for_status()
        stored = 0
        for ws in db.unscoped_workspaces():
            workspace_id = str(ws["id"])
            key = store.put_raw(SOURCE, workspace_id, run_id, "json", response.content, datetime.now(UTC).date())
            process(db, store, workspace_id, key)
            stored += 1
        return {"run_id": run_id, "workspaces": stored}
    finally:
        engine.dispose()
