"""Scenario 7: report pending → done / no data / fatal.

Must observe: resumes from the saved stage; never re-requested; terminal states distinct."""

import itertools

import pytest

from jobs.sync.contract import ReportState, RunKind, RunStatus, Stage
from jobs.sync.testing import Fault, FaultPlan, FaultRule

from . import thresholds as T
from .harness import DAY, START, Harness, WorkerKilled

Q, P, D = ReportState.QUEUED, ReportState.PROCESSING, ReportState.DONE


def _report(h: Harness):  # type: ignore[no-untyped-def]
    return h.submit(h.spec(kind=RunKind.REPORT))


def test_pending_then_done(implementations: Harness) -> None:
    h = implementations
    run_id = _report(h)
    h.drain()

    run = h.run(run_id)
    assert run.status is RunStatus.SUCCEEDED
    assert run.checkpoint["report_state"] == "done"
    assert h.report.requests == T.MAX_REPORT_REQUESTS_PER_RUN
    assert [op for op, _ in h.report.calls] == ["request_report", "report_status", "report_status",
                                               "report_status", "download"]
    assert len(h.records()) == 3
    assert h.coverage() == (START, START + DAY)
    hist = h.engine.history
    gaps = [(b.at - a.finished_at).total_seconds() for a, b in itertools.pairwise(hist)]
    assert all(g >= T.REPORT_POLL_INTERVAL_S for g in gaps)


def test_resumes_from_the_saved_stage_after_a_crash(implementations: Harness) -> None:
    h = implementations
    run_id = _report(h)
    h.kill.arm("checkpoint", on_call=2)  # dies right after saving the report id
    with pytest.raises(WorkerKilled):
        h.drain()
    assert h.run(run_id).stage is Stage.REQUESTED
    h.recover_stalled()
    h.drain()

    assert h.run(run_id).status is RunStatus.SUCCEEDED
    assert h.report.requests == 1


def test_transient_poll_errors_never_re_request(implementations: Harness) -> None:
    h = implementations
    h.report.faults = FaultPlan([FaultRule(Fault.SERVER_ERROR, at_call=2, times=2,
                                           operation="report_status"),
                                 FaultRule(Fault.TIMEOUT, at_call=1, times=1000, operation="download")])
    run_id = _report(h)
    h.drain()
    assert h.report.requests == 1
    assert h.run_row(run_id).error_code == "transient_exhausted"


def test_death_between_request_and_saving_the_id_is_not_re_requested(implementations: Harness) -> None:
    h = implementations
    original = h.report.request_report

    def request_then_die(*args: object) -> str:
        original(*args)  # type: ignore[arg-type]
        raise WorkerKilled("after request")

    h.report.request_report = request_then_die  # type: ignore[method-assign]
    run_id = _report(h)
    with pytest.raises(WorkerKilled):
        h.drain()
    h.report.request_report = original  # type: ignore[method-assign]
    h.recover_stalled()
    h.drain()

    assert h.report.requests == 1
    assert h.run_row(run_id).error_code == "report_request_lost"


def test_terminal_states_are_distinct(implementations: Harness) -> None:
    h = implementations
    results = {}
    for terminal in (ReportState.DONE, ReportState.CANCELLED_NO_DATA, ReportState.FATAL):
        h.report.script = (Q, terminal)
        day = {ReportState.DONE: 0, ReportState.CANCELLED_NO_DATA: 1, ReportState.FATAL: 2}[terminal]
        from jobs.sync.contract import Window
        run_id = h.submit(h.spec(kind=RunKind.REPORT,
                                 window=Window(START + day * DAY, START + (day + 1) * DAY)))
        h.drain()
        row = h.run_row(run_id)
        results[terminal] = (row.status, row.checkpoint.get("report_state"), row.records_accepted,
                             row.error_code)

    assert results[ReportState.DONE] == (RunStatus.SUCCEEDED, "done", 3, None)
    assert results[ReportState.CANCELLED_NO_DATA] == (RunStatus.SUCCEEDED, "cancelled_no_data", 0, None)
    assert results[ReportState.FATAL] == (RunStatus.FAILED, "fatal", 0, "report_fatal")
    assert h.coverage() == (START, START + 2 * DAY)  # done + no-data covered; fatal did not advance
    assert h.report.requests == 3


def test_a_report_that_never_finishes_fails_boundedly(implementations: Harness) -> None:
    h = implementations
    h.report.script = (P,)
    run_id = _report(h)
    h.drain()
    assert h.run_row(run_id).error_code == "report_poll_exhausted"
    assert sum(op == "report_status" for op, _ in h.report.calls) == T.MAX_REPORT_POLLS
    assert h.report.requests == 1
