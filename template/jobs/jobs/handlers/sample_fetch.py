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
    """Fetch a public value once, then per workspace: raw to storage first, then one row parsed from storage."""
    db = ScopedDb(create_engine(os.environ["DATABASE_URL"]))
    s3 = boto3.client("s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL"))
    store = RawStore(os.environ["RAW_BUCKET"], s3)
    run_id = uuid.uuid4().hex
    response = httpx.get(FEED, timeout=10.0)
    response.raise_for_status()
    stored = 0
    for ws in db.unscoped_workspaces():
        key = store.put_raw("zen", str(ws["id"]), run_id, "txt", response.content, datetime.now(UTC).date())
        db.execute(
            "insert into sample_rows (workspace_id, raw_key, value) values (:workspace_id, :raw_key, :value)",
            {"workspace_id": ws["id"], "raw_key": key, "value": store.get(key).decode().strip()},
        )
        stored += 1
    return {"run_id": run_id, "workspaces": stored}
