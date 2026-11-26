"""PgCredentialStore and the shared ciphertext format (jobs side). Synthetic keys and tokens only."""
# ruff: noqa: S105, S107  (every token here is a synthetic test value)

import base64
import json
import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import Engine, text

from jobs.sync.contract import AuthRevoked, ConnectionState, Credential, TransientError
from jobs.sync.credentials import (
    CredentialNotFound,
    KmsKeyWrapper,
    LocalKeyWrapper,
    PgCredentialStore,
    Secret,
    Vault,
    VaultError,
    VaultMisconfigured,
    connection_state,
    vault_from_env,
)

# ---- Shared test vector: the same constants are in backend/tests/test_vault.py. Both sides must open
# these exact bytes, which proves backend-sealed credentials open in the worker and back.
VECTOR_KEK_B64 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="  # bytes 0..31, synthetic
VECTOR_CONNECTION_ID = uuid.UUID("00000000-0000-4000-8000-0000000000c3")
VECTOR_TOKEN = "synthetic-access-token-vector"
VECTOR_EXTRA = {"refresh_token": "synthetic-refresh-vector"}
VECTOR_LOCAL_HEX = (
    "43560101003c0a2ffd4765decffd76fbe712b5ec21b3048b4aa0798f392ce07ad4055b014d10eef5d1f20efb15854b646b"
    "8eed5eda9ec43b9f219e1af6ba6c27890e151d47f6d59e4bcc94bf357a475163f46e7aba2a3505b35508ceb9ded197e801"
    "1236e76c6c2efac364ea260de84750d5ab78779140d45cb0122cfdc38b83a052bc0be2da140326e3a9d7c1e015e61214e2"
    "4eb286c1c8884787a93803e4b345cd4316a8d8f4723275a4d3b7cf00651e0e67c7c928753a1efa3ea36fbbdaa588c767")
VECTOR_KMS_DEK = bytes([7]) * 32
VECTOR_KMS_BLOB = b"synthetic-kms-wrapped-key"
VECTOR_KMS_HEX = (
    "43560102001973796e7468657469632d6b6d732d777261707065642d6b65795e3f1e163cfbed2ec7e384e1c184a3b56308"
    "46f93abf7549b26f2d21bf592e5b0fd849649cc433e13eaae63c45b532f81f4af536f7168bc0b6e3ec1fa7e252d5b8491a"
    "e1bf44bebaaade61e7ebd487707a803f54eb57627f9052e74ad3d54923b5c6bbe55e8453d77b12876f47330db311607b4d"
    "813da58b9570f72f4176ad935c")


class VectorKms:
    """Answers only for the vector's wrapped key and encryption context."""

    def generate_data_key(self, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("not used")

    def decrypt(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["CiphertextBlob"] == VECTOR_KMS_BLOB
        assert kwargs["EncryptionContext"] == {"purpose": "connector-credential",
                                               "connection_id": str(VECTOR_CONNECTION_ID)}
        return {"Plaintext": VECTOR_KMS_DEK}


def local_vault() -> Vault:
    return vault_from_env({"CONNECTOR_LOCAL_KEK": VECTOR_KEK_B64})


def test_shared_vector_opens_with_the_local_key() -> None:
    secret = local_vault().open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_LOCAL_HEX))
    assert secret.access_token == VECTOR_TOKEN
    assert dict(secret.extra) == VECTOR_EXTRA
    assert local_vault().key_id == "local:630dcd2966c43366"


def test_shared_vector_opens_with_kms() -> None:
    vault = Vault(KmsKeyWrapper(VectorKms(), "alias/synthetic"))
    secret = vault.open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_KMS_HEX))
    assert (secret.access_token, dict(secret.extra)) == (VECTOR_TOKEN, VECTOR_EXTRA)


def test_seal_open_round_trip_uses_a_fresh_data_key_each_time() -> None:
    vault, cid = local_vault(), uuid.uuid4()
    a = vault.seal(cid, Secret("synthetic-a"))
    b = vault.seal(cid, Secret("synthetic-a"))
    assert a != b
    assert vault.open(cid, a).access_token == "synthetic-a"
    assert b"synthetic-a" not in a


@pytest.mark.parametrize("mutate", [
    lambda b: b[:-1] + bytes([b[-1] ^ 1]),  # body
    lambda b: b[:10] + bytes([b[10] ^ 1]) + b[11:],  # wrapped key
    lambda b: b[:3] + bytes([2]) + b[4:],  # wrapper kind
    lambda b: b[:20],  # truncated
])
def test_tampered_ciphertext_is_refused(mutate: Any) -> None:
    blob = mutate(bytes.fromhex(VECTOR_LOCAL_HEX))
    with pytest.raises(VaultError) as info:
        local_vault().open(VECTOR_CONNECTION_ID, blob)
    assert VECTOR_TOKEN not in str(info.value)


def test_ciphertext_is_bound_to_its_connection() -> None:
    with pytest.raises(VaultError):
        local_vault().open(uuid.uuid4(), bytes.fromhex(VECTOR_LOCAL_HEX))


def test_a_different_local_key_cannot_open() -> None:
    other = Vault(LocalKeyWrapper(bytes(32)))
    with pytest.raises(VaultError):
        other.open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_LOCAL_HEX))


def test_production_refuses_the_local_key() -> None:
    with pytest.raises(VaultMisconfigured) as info:
        vault_from_env({"CONNECTOR_LOCAL_KEK": VECTOR_KEK_B64, "APP_ENV": "production"})
    assert VECTOR_KEK_B64 not in str(info.value)
    with pytest.raises(VaultMisconfigured):
        PgCredentialStore.from_env(None, {"CONNECTOR_LOCAL_KEK": VECTOR_KEK_B64,  # type: ignore[arg-type]
                                          "APP_ENV": "production"})


@pytest.mark.parametrize("value", ["", "not base64!", base64.b64encode(b"short").decode()])
def test_bad_or_missing_local_key_is_refused_without_echoing_it(value: str) -> None:
    with pytest.raises(VaultMisconfigured) as info:
        vault_from_env({"CONNECTOR_LOCAL_KEK": value})
    assert not value or value not in str(info.value)


@mock_aws
def test_kms_round_trip_with_moto() -> None:
    kms = boto3.client("kms", region_name="us-east-1")
    key_id = kms.create_key(Description="synthetic connector key")["KeyMetadata"]["KeyId"]
    vault = vault_from_env({"CONNECTOR_KMS_KEY_ID": key_id, "APP_ENV": "production"}, kms_client=kms)
    cid = uuid.uuid4()
    blob = vault.seal(cid, Secret("synthetic-kms", {"k": "v"}))
    assert vault.key_id == f"kms:{key_id}"
    assert vault.open(cid, blob).access_token == "synthetic-kms"
    with pytest.raises(VaultError) as info:  # encryption context binds the data key to the connection
        vault.open(uuid.uuid4(), blob)
    assert "synthetic-kms" not in str(info.value)


# ---- PgCredentialStore on Postgres


@pytest.fixture
def store(clean_tables: Engine) -> PgCredentialStore:
    return PgCredentialStore(clean_tables, local_vault())


def seed(engine: Engine, vault: Vault, workspace_id: str, token: str = "synthetic-token-1",
         state: str = "healthy") -> uuid.UUID:
    cid = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text(
            "insert into connections (id, workspace_id, provider, account_ref, display_name, state)"
            " values (:id, :ws, 'synthetic', :ref, 'Synthetic', :state)"),
            {"id": cid, "ws": workspace_id, "ref": f"acct-{cid}", "state": state})
        conn.execute(text("insert into credentials (connection_id, ciphertext, key_id, version, expires_at)"
                          " values (:id, :blob, :key_id, 1, :exp)"),
                     {"id": cid, "blob": vault.seal(cid, Secret(token, {"refresh_token": "synthetic-r"})),
                      "key_id": vault.key_id, "exp": datetime(2030, 1, 1, tzinfo=UTC)})
    return cid


def test_get_decrypts(store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    cred = store.get(cid)
    assert (cred.access_token, cred.version, dict(cred.extra)) == ("synthetic-token-1", 1,
                                                                    {"refresh_token": "synthetic-r"})
    assert cred.expires_at == datetime(2030, 1, 1, tzinfo=UTC)
    with pytest.raises(CredentialNotFound):
        store.get(uuid.uuid4())


def test_rotate_writes_a_new_version(store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    exp = datetime.now(UTC) + timedelta(hours=1)
    new = store.rotate(store.get(cid), "synthetic-token-2", exp)
    assert (new.access_token, new.version, dict(new.extra)) == ("synthetic-token-2", 2,
                                                                 {"refresh_token": "synthetic-r"})
    assert store.get(cid) == new
    with store.engine.connect() as conn:
        row = conn.execute(text("select ciphertext, refreshed_at from credentials where connection_id = :id"),
                           {"id": cid}).one()
    assert b"synthetic-token-2" not in bytes(row.ciphertext)
    assert row.refreshed_at is not None


def test_rotate_with_a_stale_version_returns_the_newer_and_overwrites_nothing(
        store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    old = store.get(cid)
    winner = store.rotate(old, "synthetic-winner", None, {"refresh_token": "synthetic-r2"})
    loser = store.rotate(old, "synthetic-loser", None)
    assert loser == winner
    assert store.get(cid).access_token == "synthetic-winner"
    assert store.get(cid).version == 2


def test_concurrent_refresh_has_exactly_one_winner(store: PgCredentialStore,
                                                   two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    start = store.get(cid)
    results: list[Credential] = []
    barrier = threading.Barrier(6)

    def refresh(n: int) -> None:
        barrier.wait()
        results.append(store.rotate(start, f"synthetic-worker-{n}", None))

    threads = [threading.Thread(target=refresh, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = store.get(cid)
    assert final.version == 2
    assert all(r == final for r in results)


def audit_rows(engine: Engine, cid: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text("select * from audit_events where target_id = :t"), {"t": str(cid)}))


def test_mark_revoked_needs_reconnect_and_audits_once(store: PgCredentialStore,
                                                      two_workspaces: tuple[str, str]) -> None:
    ws = two_workspaces[0]
    cid = seed(store.engine, store.vault, ws)
    store.mark_revoked(cid, "provider_auth_revoked")
    store.mark_revoked(cid, "provider_auth_revoked")
    with store.engine.connect() as conn:
        conn_row = conn.execute(text("select state, state_reason from connections where id = :id"),
                                {"id": cid}).one()
        revoked_at = conn.execute(text("select revoked_at from credentials where connection_id = :id"),
                                  {"id": cid}).scalar_one()
    assert (conn_row.state, conn_row.state_reason) == ("reconnect_needed", "provider_auth_revoked")
    assert revoked_at is not None
    events = audit_rows(store.engine, cid)
    assert len(events) == 1
    e = events[0]
    assert (str(e.workspace_id), e.actor_type, e.action, e.target_type) == (
        ws, "system", "connection.auth_revoked", "connection")
    assert e.detail == {"from_state": "healthy", "reason": "provider_auth_revoked"}
    with pytest.raises(AuthRevoked):
        store.get(cid)


def test_mark_revoked_leaves_a_disconnected_connection_alone(store: PgCredentialStore,
                                                             two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0], state="disconnected")
    store.mark_revoked(cid, "x")
    with store.engine.connect() as conn:
        assert conn.execute(text("select state from connections where id = :id"),
                            {"id": cid}).scalar_one() == "disconnected"
    assert audit_rows(store.engine, cid) == []


def test_mark_revoked_trims_the_reason(store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    store.mark_revoked(cid, "r" * 1000)
    (event,) = audit_rows(store.engine, cid)
    assert len(json.dumps(event.detail)) < 300


def test_rotate_refuses_a_revoked_connection(store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    cred = store.get(cid)
    store.mark_revoked(cid, "provider_auth_revoked")
    with pytest.raises(AuthRevoked):
        store.rotate(cred, "synthetic-late", None)


# ---- refresh (serialized provider call) and connection_state


class CountingRefresher:
    """A synthetic provider refresh. `delay_s` widens the race window; `error` is raised instead."""

    def __init__(self, delay_s: float = 0.0, error: Exception | None = None) -> None:
        self.calls: list[Credential] = []
        self.delay_s = delay_s
        self.error = error
        self._lock = threading.Lock()

    def refresh_token(self, cred: Credential) -> tuple[str, datetime | None]:
        with self._lock:
            self.calls.append(cred)
            n = len(self.calls)
        time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return f"synthetic-refreshed-{n}", datetime(2031, 1, 1, tzinfo=UTC)


def test_refresh_calls_the_provider_once_and_saves_a_new_version(
        store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    start = store.get(cid)
    refresher = CountingRefresher()
    new = store.refresh(start, refresher)
    assert refresher.calls == [start]
    assert (new.access_token, new.version, dict(new.extra)) == ("synthetic-refreshed-1", 2,
                                                                 {"refresh_token": "synthetic-r"})
    assert new.expires_at == datetime(2031, 1, 1, tzinfo=UTC)
    assert store.get(cid) == new


def test_refresh_with_a_stale_version_returns_the_newer_without_calling_the_provider(
        store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    old = store.get(cid)
    newer = store.refresh(old, CountingRefresher())
    refresher = CountingRefresher()
    assert store.refresh(old, refresher) == newer
    assert refresher.calls == []


def test_two_workers_refreshing_at_once_call_the_provider_exactly_once(
        store: PgCredentialStore, two_workspaces: tuple[str, str], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    cid = seed(store.engine, store.vault, two_workspaces[0])
    start = store.get(cid)
    refresher = CountingRefresher(delay_s=0.3)  # the winner holds the lock across a slow provider call
    results: list[Credential] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        try:
            results.append(store.refresh(start, refresher))
        except BaseException as exc:  # surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(refresher.calls) == 1
    final = store.get(cid)
    assert final.version == 2 and final.access_token == "synthetic-refreshed-1"
    assert results == [final, final]
    for token in ("synthetic-token-1", "synthetic-refreshed-1", "synthetic-r"):
        assert token not in caplog.text


def test_auth_revoked_from_the_provider_propagates_and_writes_nothing(
        store: PgCredentialStore, two_workspaces: tuple[str, str], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    cid = seed(store.engine, store.vault, two_workspaces[0])
    start = store.get(cid)
    with pytest.raises(AuthRevoked) as info:
        store.refresh(start, CountingRefresher(error=AuthRevoked("refresh rejected", request_ref="req-1")))
    assert store.get(cid) == start  # nothing written
    store.mark_revoked(cid, "provider_auth_revoked")  # what the caller does next
    assert connection_state(store.engine, cid) is ConnectionState.RECONNECT_NEEDED
    refresher = CountingRefresher()
    with pytest.raises(AuthRevoked) as again:  # a revoked connection is never refreshed
        store.refresh(start, refresher)
    assert refresher.calls == []
    for text_ in (str(info.value), repr(info.value), str(again.value), caplog.text):
        assert "synthetic-token-1" not in text_ and "synthetic-r" not in text_


def test_other_provider_errors_propagate_and_the_next_refresh_still_works(
        store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    cid = seed(store.engine, store.vault, two_workspaces[0])
    start = store.get(cid)
    with pytest.raises(TransientError):
        store.refresh(start, CountingRefresher(error=TransientError("timeout")))
    assert store.refresh(start, CountingRefresher()).version == 2  # the lock was released


def test_refresh_holds_the_lock_only_per_connection(store: PgCredentialStore,
                                                    two_workspaces: tuple[str, str]) -> None:
    a = seed(store.engine, store.vault, two_workspaces[0])
    b = seed(store.engine, store.vault, two_workspaces[1])
    slow = CountingRefresher(delay_s=0.5)
    t = threading.Thread(target=store.refresh, args=(store.get(a), slow))
    t.start()
    time.sleep(0.1)
    began = time.monotonic()
    store.refresh(store.get(b), CountingRefresher())
    assert time.monotonic() - began < 0.4  # b didn't wait for a's provider call
    t.join()


def test_connection_state(store: PgCredentialStore, two_workspaces: tuple[str, str]) -> None:
    ws = two_workspaces[0]
    assert connection_state(store.engine, seed(store.engine, store.vault, ws)) is ConnectionState.HEALTHY
    paused = seed(store.engine, store.vault, ws, state="paused")
    assert connection_state(store.engine, paused) is ConnectionState.PAUSED
    assert connection_state(store.engine, uuid.uuid4()) is ConnectionState.DISCONNECTED
