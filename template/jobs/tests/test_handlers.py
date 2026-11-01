import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import httpx
import pytest
import respx
from moto import mock_aws
from sqlalchemy import Engine, create_engine, text

from jobs.db import ScopedDb
from jobs.handlers import billing_reconcile, sample_fetch

LAGO = "http://lago.test"


@dataclass
class FakeLago:
    """Lago v1.55.0 as reconcile sees it: GET by external id finds only the `?status=` asked for."""

    subscriptions: dict[str, str] = field(default_factory=dict)  # external id -> Lago status
    latest_payment: dict[str, str] = field(default_factory=dict)  # customer -> latest invoice payment_status
    cards: set[str] = field(default_factory=set)  # customers with a default payment method
    down: set[str] = field(default_factory=set)  # external ids whose lookup answers 500
    garbled: set[str] = field(default_factory=set)  # external ids whose lookup answers 200 non-JSON
    already_incomplete: set[str] = field(default_factory=set)  # create answers 422 subscription_incomplete
    rejected: set[str] = field(default_factory=set)  # create answers 422 no_default_payment_method
    created: list[dict[str, Any]] = field(default_factory=list)  # every create attempt

    def get_subscription(self, request: httpx.Request, external_id: str) -> httpx.Response:
        if external_id in self.down:
            return httpx.Response(500)
        if external_id in self.garbled:
            return httpx.Response(200, text="<html>proxy</html>")
        status = request.url.params.get("status", "active")
        if self.subscriptions.get(external_id) != status:
            return httpx.Response(404, json={"status": 404, "error": "Not Found", "code": "subscription_not_found"})
        return httpx.Response(200, json={"subscription": {"external_id": external_id, "status": status}})

    def list_invoices(self, request: httpx.Request) -> httpx.Response:
        assert request.url.params["invoice_type"] == "subscription"
        assert request.url.params["status"] == "finalized"
        status = self.latest_payment.get(request.url.params["external_customer_id"])
        invoices = [{"lago_id": "inv-1", "payment_status": status}] if status else []
        return httpx.Response(200, json={"invoices": invoices, "meta": {}})

    def payment_methods(self, request: httpx.Request, customer: str) -> httpx.Response:
        methods = [{"lago_id": "pm-1", "is_default": True}] if customer in self.cards else []
        return httpx.Response(200, json={"payment_methods": methods, "meta": {}})

    def create(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)["subscription"]
        self.created.append(body)
        if body["external_id"] in self.rejected:
            return httpx.Response(422, json={"status": 422, "error": "Unprocessable Entity", "code": "validation_errors",
                                             "error_details": {"customer": ["no_default_payment_method"]}})
        if body["external_id"] in self.already_incomplete:
            return httpx.Response(422, json={"status": 422, "error": "Unprocessable Entity", "code": "validation_errors",
                                             "error_details": {"subscription": ["subscription_incomplete"]}})
        self.subscriptions[body["external_id"]] = "incomplete"
        return httpx.Response(200, json={"subscription": {**body, "status": "incomplete"}})

    def client(self, router: respx.Router) -> billing_reconcile.Lago:
        router.get(path__regex=r"^/api/v1/subscriptions/(?P<external_id>[^/]+)$").mock(side_effect=self.get_subscription)
        router.get(path="/api/v1/invoices").mock(side_effect=self.list_invoices)
        router.get(path__regex=r"^/api/v1/customers/(?P<customer>[^/]+)/payment_methods$").mock(side_effect=self.payment_methods)
        router.post(path="/api/v1/subscriptions").mock(side_effect=self.create)
        return billing_reconcile.Lago(httpx.Client(base_url=LAGO))


@pytest.fixture
def router() -> Iterator[respx.Router]:
    with respx.mock(base_url=LAGO, assert_all_called=False) as mock:
        yield mock


def _db(rows: list[tuple[str, str, str | None, str | None]], workspaces: dict[str, str]) -> Engine:
    """rows: (workspace, state, lago_external_id, lago_subscription_id), plan `starter`."""
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table workspaces (id text, status text)")
        c.exec_driver_sql("create table subscriptions (workspace_id text, plan_code text, state text,"
                          " lago_external_id text, lago_subscription_id text, updated_at text)")
        for ws, status in workspaces.items():
            c.execute(text("insert into workspaces values (:w, :s)"), {"w": ws, "s": status})
        for ws, state, ext, lago_id in rows:
            c.execute(text("insert into subscriptions values (:w, 'starter', :s, :x, :l, '')"),
                      {"w": ws, "s": state, "x": ext, "l": lago_id})
    return engine


def _rows(engine: Engine) -> dict[str, tuple[str, str | None, bool]]:
    """workspace -> (state, lago_subscription_id, updated_at bumped)."""
    with engine.connect() as c:
        rows = c.execute(text("select workspace_id, state, lago_subscription_id, updated_at from subscriptions")).all()
    return {ws: (state, lago_id, updated != "") for ws, state, lago_id, updated in rows}


def test_reconcile_repairs_states(router: respx.Router) -> None:
    ids = {ws: f"{ws}:starter:0000000{n}" for n, ws in enumerate("abcdefgx")}
    states = {"a": "pending", "b": "past_due", "c": "active", "d": "active", "e": "past_due",
              "f": "active", "g": "canceled", "x": "pending"}
    engine = _db([(ws, states[ws], ids[ws], ids[ws]) for ws in states],
                 {**dict.fromkeys("abcdefgy", "ready"), "x": "creating"})
    lago = FakeLago(
        subscriptions={ids["a"]: "active", ids["b"]: "active", ids["c"]: "terminated", ids["e"]: "active",
                       ids["f"]: "active", ids["x"]: "active"},
        latest_payment={"a": "succeeded", "b": "failed", "e": "succeeded", "f": "failed"},
        down={ids["d"]},
    )
    result = billing_reconcile.reconcile(ScopedDb(engine), lago.client(router))
    assert {ws: row[0] for ws, row in _rows(engine).items()} == {
        "a": "active",  # pending, first invoice paid, webhook missed
        "b": "past_due",  # still failing
        "c": "canceled",  # terminated in Lago
        "d": "active",  # Lago unavailable: unchanged
        "e": "active",  # retry paid, webhook missed (or a late payment_failure stranded it)
        "f": "past_due",  # payment failed, webhook missed
        "g": "canceled",  # not found in Lago under any status: unchanged
        "x": "pending",  # workspace still creating: not visited
    }
    assert result == {"checked": 7, "changed": 4, "errors": 1}
    assert {ws for ws, row in _rows(engine).items() if row[2]} == {"a", "c", "e", "f"}


def test_reconcile_finishes_started_checkouts(router: respx.Router) -> None:
    ext = {ws: f"{ws}:starter:abcdef0{n}" for n, ws in enumerate("hijkl")}
    engine = _db([(ws, "pending", ext[ws], None) for ws in ext], dict.fromkeys(ext, "ready"))
    lago = FakeLago(
        subscriptions={ext["k"]: "active"},  # created, response lost, first invoice paid
        latest_payment={"k": "succeeded"},
        cards={"h", "j", "k", "l"},  # i never saved a card
        already_incomplete={ext["j"]},
        rejected={ext["l"]},
    )
    result = billing_reconcile.reconcile(ScopedDb(engine), lago.client(router))
    assert _rows(engine) == {
        "h": ("pending", ext["h"], True),  # gated subscription created; the invoice-paid webhook grants access
        "i": ("pending", None, False),
        "j": ("pending", ext["j"], True),  # repeat create: 422 subscription_incomplete counts as done
        "k": ("active", ext["k"], True),
        "l": ("pending", None, False),  # Lago refused: retried next run
    }
    assert lago.created == [
        {"external_customer_id": ws, "plan_code": "starter", "external_id": ext[ws],
         "activation_rules": [{"type": "payment", "timeout_hours": 48}]}
        for ws in "hjl"
    ]
    assert result == {"checked": 5, "changed": 3, "errors": 1}


def test_reconcile_loses_to_a_concurrent_webhook(router: respx.Router, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _db([("a", "pending", "a:starter:00000000", "a:starter:00000000")], {"a": "ready"})
    lago = FakeLago(subscriptions={"a:starter:00000000": "active"}, latest_payment={"a": "succeeded"})
    client = lago.client(router)
    real_status = client.subscription_status

    def webhook_lands_meanwhile(external_id: str) -> str | None:
        with engine.begin() as c:
            c.exec_driver_sql("update subscriptions set state = 'canceled'")
        return real_status(external_id)

    monkeypatch.setattr(client, "subscription_status", webhook_lands_meanwhile)
    assert billing_reconcile.reconcile(ScopedDb(engine), client) == {"checked": 1, "changed": 0, "errors": 0}
    assert _rows(engine)["a"][0] == "canceled"


@pytest.mark.parametrize(
    ("state", "lago_status", "latest", "expected"),
    [
        ("active", "incomplete", None, "pending"),
        ("active", "pending", None, "pending"),
        ("active", "canceled", None, "canceled"),
        ("past_due", "active", "pending", "past_due"),  # payment retry in flight: keep
        ("past_due", "active", None, "past_due"),
    ],
)
def test_reconcile_maps_lago_status(router: respx.Router, state: str, lago_status: str,
                                    latest: str | None, expected: str) -> None:
    engine = _db([("a", state, "a:starter:00000000", "a:starter:00000000")], {"a": "ready"})
    lago = FakeLago(subscriptions={"a:starter:00000000": lago_status},
                    latest_payment={"a": latest} if latest else {})
    billing_reconcile.reconcile(ScopedDb(engine), lago.client(router))
    assert _rows(engine)["a"][0] == expected


def test_reconcile_skips_rows_without_any_lago_id(router: respx.Router) -> None:
    engine = _db([("a", "pending", None, None)], {"a": "ready"})
    lago = FakeLago(cards={"a"})
    assert billing_reconcile.reconcile(ScopedDb(engine), lago.client(router)) == {"checked": 1, "changed": 0, "errors": 0}
    assert lago.created == []
    assert not router.calls


def test_reconcile_adopts_a_lost_create_that_was_canceled(router: respx.Router) -> None:
    engine = _db([("a", "pending", "a:starter:00000000", None)], {"a": "ready"})
    lago = FakeLago(subscriptions={"a:starter:00000000": "canceled"}, cards={"a"})
    assert billing_reconcile.reconcile(ScopedDb(engine), lago.client(router)) == {"checked": 1, "changed": 1, "errors": 0}
    assert _rows(engine)["a"] == ("canceled", "a:starter:00000000", True)
    assert lago.created == []


def test_reconcile_counts_an_unreadable_answer_as_an_error(router: respx.Router) -> None:
    engine = _db([("a", "active", "a:starter:00000000", "a:starter:00000000"),
                  ("b", "pending", "b:starter:00000000", "b:starter:00000000")], {"a": "ready", "b": "ready"})
    lago = FakeLago(subscriptions={"b:starter:00000000": "active"}, latest_payment={"b": "succeeded"})
    lago.garbled.add("a:starter:00000000")
    assert billing_reconcile.reconcile(ScopedDb(engine), lago.client(router)) == {"checked": 2, "changed": 1, "errors": 1}
    assert _rows(engine)["b"][0] == "active"


FEED_BODY = b'{"amount":1.0,"base":"USD","date":"2026-10-30","rates":{"EUR":0.89509}}'


@pytest.fixture
def sample_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """sqlite with the 0003 shape (unique raw_key), moto S3 with bucket `raw`, and the feed faked."""
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = create_engine(url)
    with engine.begin() as c:
        c.exec_driver_sql("create table workspaces (id text, status text)")
        c.exec_driver_sql("insert into workspaces values ('a', 'ready'), ('b', 'ready'), ('c', 'creating')")
        c.exec_driver_sql("create table sample_rows (id integer primary key, workspace_id text not null,"
                          " raw_key text not null unique, value text not null)")
    for name, value in {"DATABASE_URL": url, "RAW_BUCKET": "raw", "AWS_ACCESS_KEY_ID": "testing",
                        "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    with mock_aws(), respx.mock:
        respx.get(sample_fetch.FEED).respond(200, content=FEED_BODY)
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="raw")
        yield engine
    engine.dispose()


def _sample_rows(engine: Engine) -> list[tuple[str, str, str]]:
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text("select workspace_id, raw_key, value from sample_rows order by workspace_id"))]


def test_sample_fetch_stores_raw_then_one_row_per_workspace(sample_env: Engine) -> None:
    result = sample_fetch.handler({}, None)
    day = datetime.now(UTC).strftime("%Y/%m/%d")
    assert result == {"run_id": result["run_id"], "workspaces": 2}
    rows = _sample_rows(sample_env)
    assert rows == [(ws, f"raw/fx/{ws}/{day}/{result['run_id']}.json", "0.89509") for ws in "ab"]
    s3 = boto3.client("s3", region_name="us-east-1")
    assert s3.get_object(Bucket="raw", Key=rows[0][1])["Body"].read() == FEED_BODY


def test_sample_fetch_reprocesses_from_storage(sample_env: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    sample_fetch.handler({}, None)
    key = _sample_rows(sample_env)[0][1]
    monkeypatch.setattr(sample_fetch, "parse", lambda raw: f"EUR {json.loads(raw)['rates']['EUR']}")  # the parsing fix
    assert sample_fetch.handler({"reprocess": [key]}, None) == {"reprocessed": 1}
    assert [r for r in _sample_rows(sample_env) if r[0] == "a"] == [("a", key, "EUR 0.89509")]
    assert len(_sample_rows(sample_env)) == 2


def test_sample_fetch_empty_reprocess_list_fetches_nothing(sample_env: Engine) -> None:
    assert sample_fetch.handler({"reprocess": []}, None) == {"reprocessed": 0}
    assert not respx.calls
    assert _sample_rows(sample_env) == []


@pytest.mark.parametrize("key", ["raw/zen/a/2026/10/31/r.json", "raw/fx//2026/10/31/r.json", "other/fx/a/x"])
def test_sample_fetch_refuses_foreign_keys(sample_env: Engine, key: str) -> None:
    with pytest.raises(ValueError, match="not a raw fx key"):
        sample_fetch.handler({"reprocess": [key]}, None)


def test_s3_client_is_path_style_for_a_local_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://seaweedfs:8333")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    s3 = sample_fetch.s3_client()
    assert s3.meta.config.s3 == {"addressing_style": "path"}
    assert s3.meta.endpoint_url == "http://seaweedfs:8333"
