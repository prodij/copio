"""A paginated incremental feed (and one snapshot dataset) with deterministic fault injection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jobs.sync.contract import AuthRevoked, Credential, Page, Record, Window
from jobs.sync.testing.faults import Fault, FaultPlan, SchemaChanged, raise_for
from jobs.sync.testing.world import SNAPSHOT_DATASETS, SyntheticWorld

TOKEN_LIFETIME_END = datetime(2100, 1, 1, tzinfo=UTC)


def encode_body(*, schema: int, items: Sequence[dict[str, Any]], next_cursor: str | None,
                complete: bool, request_id: str) -> bytes:
    return json.dumps({"schema": schema, "items": list(items), "next": next_cursor,
                       "complete": complete, "request_id": request_id},
                      sort_keys=True).encode()


def parse_body(raw: bytes, *, connector_version: str) -> Page:
    """Parse a synthetic body. Connector version "1" understands schema 1; version "2" both."""
    body = json.loads(raw)
    schema = body.get("schema")
    if schema not in (1, 2) or (schema == 2 and connector_version == "1"):
        raise SchemaChanged("response schema not supported by this connector version", raw=raw,
                            request_ref=body.get("request_id"))
    records = []
    for item in body["items"]:
        data = item["data"] if schema == 1 else item["attrs"]
        records.append(Record(key=item["id"], version=item["v"], data=data,
                              deleted=bool(item.get("deleted", False))))
    return Page(records=records, next_cursor=body["next"], raw=raw,
                request_ref=body.get("request_id"), complete_snapshot=bool(body["complete"]))


@dataclass
class SyntheticFeed:
    """Implements `Provider` and `TokenRefresher`."""

    world: SyntheticWorld
    faults: FaultPlan = field(default_factory=FaultPlan)
    page_size: int = 4
    name: str = "synthetic-feed"
    version: str = "1"
    schema: int = 1  # the schema the provider serves now; 2 imitates a provider-side change
    calls: list[tuple[str, str | None]] = field(default_factory=list)
    refreshes: int = 0

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _call(self, operation: str, detail: str | None, cred: Credential) -> Fault | None:
        self.calls.append((operation, detail))
        self.world.on_call()
        n = len(self.calls)
        valid = self.world.valid_tokens.get(cred.connection_id)
        if valid is not None and cred.access_token not in valid:
            raise AuthRevoked(f"401 invalid token {cred.access_token}", request_ref=f"req-{n}")
        rule = self.faults.rule(n, operation)
        if rule is None:
            return None
        raise_for(rule, token=cred.access_token, budget_key=f"{self.name}:{cred.connection_id}",
                  request_ref=f"req-{n}")
        return rule.fault

    def fetch_page(self, cred: Credential, dataset: str, window: Window, cursor: str | None) -> Page:
        fault = self._call("fetch_page", cursor, cred)
        request_id = f"req-{self.call_count}"
        rows = self.world.rows(cred.connection_id, dataset, window)
        offset = int(cursor) if cursor else 0
        end = offset + self.page_size
        chunk = rows[offset:end]
        next_cursor: str | None = str(end) if end < len(rows) else None
        snapshot = dataset in SNAPSHOT_DATASETS
        complete = snapshot and next_cursor is None
        if fault is Fault.PARTIAL_SNAPSHOT:
            chunk = chunk[: max(1, len(chunk) // 2)]
            next_cursor, complete = None, False
        if fault is Fault.DUPLICATE and offset > 0:
            chunk = rows[max(0, offset - self.page_size):end]
        items = []
        for key, row in chunk:
            version = row.version
            data = dict(row.data)
            if fault is Fault.STALE_READ:
                stem, rev = version.rsplit("-", 1)
                version = f"{stem}-{max(0, int(rev) - 1):06d}"
                data["stale"] = True
            item: dict[str, Any] = {"id": key, "v": version, "deleted": row.deleted}
            item["data" if self.schema == 1 else "attrs"] = data
            items.append(item)
        schema = 2 if fault is Fault.SCHEMA_CHANGE else self.schema
        if fault is Fault.SCHEMA_CHANGE:
            for item in items:
                item["attrs"] = item.pop("data", item.get("attrs"))
        raw = encode_body(schema=schema, items=items, next_cursor=next_cursor, complete=complete,
                          request_id=request_id)
        return self.parse_page(dataset, raw)

    def parse_page(self, dataset: str, raw: bytes) -> Page:
        return parse_body(raw, connector_version=self.version)

    def refresh_token(self, cred: Credential) -> tuple[str, datetime | None]:
        """Exchange the refresh grant for a new access token (the old one stays valid here)."""
        self.calls.append(("refresh_token", None))
        self.world.on_call()
        self.refreshes += 1
        token = f"tok-{str(cred.connection_id)[:8]}-r{self.refreshes}"
        self.world.grant(cred.connection_id, token)
        return token, TOKEN_LIFETIME_END
