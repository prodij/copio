"""The synthetic world: two workspaces, each with one connected account, and their data.

Data is generated from the window, so a long backfill is large and a one-day incremental is small.
Tests change the world (a newer version, a deleted object) to imitate what happens at a provider.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from jobs.sync.contract import Window

_NS = uuid.UUID("6f1d1c55-0000-4000-8000-00000000c0c1")


@dataclass(frozen=True)
class SyntheticAccount:
    label: str
    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    account_ref: str


def _account(label: str) -> SyntheticAccount:
    return SyntheticAccount(label=label,
                            workspace_id=uuid.uuid5(_NS, f"workspace:{label}"),
                            connection_id=uuid.uuid5(_NS, f"connection:{label}"),
                            account_ref=f"acct-{label}")


SYNTHETIC_WORKSPACES: tuple[SyntheticAccount, SyntheticAccount] = (_account("a"), _account("b"))

EVENTS = "events"  # incremental: records belong to a day inside the window
ACCOUNTS = "accounts"  # snapshot: the full current set on every fetch, regardless of window
SNAPSHOT_DATASETS = frozenset({ACCOUNTS})


@dataclass
class _Row:
    version: str
    data: dict[str, object]
    deleted: bool = False


def _version(day: datetime, rev: int) -> str:
    # Lexicographic order is version order: a UTC date, then a zero-padded revision.
    return f"{day:%Y%m%d}-{rev:06d}"


@dataclass
class SyntheticWorld:
    """Per (connection, dataset) state. `per_day` events per day; `snapshot_size` accounts."""

    per_day: int = 3
    snapshot_size: int = 6
    on_call: Callable[[], None] = field(default=lambda: None)  # the test clock's latency hook
    _overrides: dict[tuple[uuid.UUID, str, str], _Row] = field(default_factory=dict)
    _removed: set[tuple[uuid.UUID, str, str]] = field(default_factory=set)
    valid_tokens: dict[uuid.UUID, set[str]] = field(default_factory=dict)

    def rows(self, connection_id: uuid.UUID, dataset: str, window: Window) -> list[tuple[str, _Row]]:
        label = str(connection_id)[:8]
        out: list[tuple[str, _Row]] = []
        if dataset == ACCOUNTS:
            anchor = datetime(2026, 1, 1)
            for i in range(self.snapshot_size):
                key = f"acct-{i:04d}"
                out.append((key, _Row(_version(anchor, 1), {"id": key, "name": f"account {i}",
                                                            "owner": label})))
        else:
            day = window.start.replace(hour=0, minute=0, second=0, microsecond=0)
            while day < window.end:
                for i in range(self.per_day):
                    key = f"{day:%Y%m%d}-{i:03d}"
                    out.append((key, _Row(_version(day, 1), {"id": key, "amount": (i + 1) * 100,
                                                             "owner": label})))
                day += timedelta(days=1)
        result: list[tuple[str, _Row]] = []
        for key, row in out:
            ident = (connection_id, dataset, key)
            if ident in self._removed:
                continue
            result.append((key, self._overrides.get(ident, row)))
        return result

    def update(self, connection_id: uuid.UUID, dataset: str, key: str, rev: int,
               data: dict[str, object]) -> str:
        """A newer version of one object appears at the provider. Returns its version string."""
        day = datetime.strptime(key[:8], "%Y%m%d") if key[:8].isdigit() else datetime(2026, 1, 1)
        version = _version(day, rev)
        self._overrides[(connection_id, dataset, key)] = _Row(version, dict(data))
        return version

    def remove(self, connection_id: uuid.UUID, dataset: str, key: str) -> None:
        """The object is gone at the provider; only a complete snapshot can reveal that."""
        self._removed.add((connection_id, dataset, key))

    def grant(self, connection_id: uuid.UUID, token: str) -> None:
        self.valid_tokens.setdefault(connection_id, set()).add(token)

    def revoke_all(self, connection_id: uuid.UUID) -> None:
        self.valid_tokens[connection_id] = set()
