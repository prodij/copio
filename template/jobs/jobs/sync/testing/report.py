"""An asynchronous report provider: request once, poll (queued → processing → terminal), download."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from jobs.sync.contract import (
    AuthRevoked,
    Credential,
    Page,
    ReportState,
    ReportStatus,
    Window,
)
from jobs.sync.testing.faults import FaultPlan, raise_for
from jobs.sync.testing.feed import encode_body, parse_body
from jobs.sync.testing.world import SyntheticWorld

DEFAULT_SCRIPT: tuple[ReportState, ...] = (ReportState.QUEUED, ReportState.PROCESSING,
                                           ReportState.DONE)


@dataclass
class _Report:
    connection_id: Any
    dataset: str
    window: Window
    polls: int = 0


@dataclass
class SyntheticReportProvider:
    """Implements `ReportProvider`, plus `parse_page` for replay.

    `script` is the sequence of states successive status calls return; the last one repeats."""

    world: SyntheticWorld
    script: Sequence[ReportState] = DEFAULT_SCRIPT
    faults: FaultPlan = field(default_factory=FaultPlan)
    name: str = "synthetic-report"
    version: str = "1"
    calls: list[tuple[str, str | None]] = field(default_factory=list)
    reports: dict[str, _Report] = field(default_factory=dict)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def requests(self) -> int:
        return sum(1 for op, _ in self.calls if op == "request_report")

    def _call(self, operation: str, detail: str | None, cred: Credential) -> None:
        self.calls.append((operation, detail))
        self.world.on_call()
        n = len(self.calls)
        valid = self.world.valid_tokens.get(cred.connection_id)
        if valid is not None and cred.access_token not in valid:
            raise AuthRevoked(f"401 invalid token {cred.access_token}", request_ref=f"req-{n}")
        rule = self.faults.rule(n, operation)
        if rule is not None:
            raise_for(rule, token=cred.access_token, budget_key=f"{self.name}:{cred.connection_id}",
                      request_ref=f"req-{n}")

    def request_report(self, cred: Credential, dataset: str, window: Window) -> str:
        self._call("request_report", dataset, cred)
        report_id = f"rpt-{len(self.reports) + 1:06d}"
        self.reports[report_id] = _Report(cred.connection_id, dataset, window)
        return report_id

    def report_status(self, cred: Credential, report_id: str) -> ReportStatus:
        self._call("report_status", report_id, cred)
        report = self.reports[report_id]
        state = self.script[min(report.polls, len(self.script) - 1)]
        report.polls += 1
        document_ref = f"doc-{report_id}" if state is ReportState.DONE else None
        return ReportStatus(state=state, document_ref=document_ref,
                            request_ref=f"req-{self.call_count}")

    def download(self, cred: Credential, document_ref: str) -> Page:
        self._call("download", document_ref, cred)
        report = self.reports[document_ref.removeprefix("doc-")]
        rows = self.world.rows(report.connection_id, report.dataset, report.window)
        items = [{"id": key, "v": row.version, "deleted": row.deleted, "data": dict(row.data)}
                 for key, row in rows]
        raw = encode_body(schema=1, items=items, next_cursor=None, complete=False,
                          request_id=f"req-{self.call_count}")
        return self.parse_page(report.dataset, raw)

    def parse_page(self, dataset: str, raw: bytes) -> Page:
        return parse_body(raw, connector_version=self.version)
