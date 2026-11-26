"""Encrypted connector credentials for the jobs worker: `PgCredentialStore` implements the contract's
`CredentialStore` on the `credentials` and `connections` tables (migration 0004).

The ciphertext format and the key wrappers between the "shared format" markers are an exact copy of
backend/app/connectors/vault.py, which seals what this module opens (see that file for the layout).
Change one, change both; the shared test vector in both test suites fails if they drift.

Refresh is serialized per connection with `pg_advisory_xact_lock`, and a rotation only writes when the
caller's version is still current, so two workers refreshing at once produce one new token and the
loser gets the winner's credential back. Nothing here logs a credential, and no exception message
carries one.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import struct
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Connection, Engine, text

from jobs.sync.contract import (
    AuthRevoked,
    ConnectionState,
    Credential,
    CredentialStore,
    TokenRefresher,
)

# --- shared format begin (identical in backend/app/connectors/vault.py) ---
MAGIC = b"CV"
FORMAT_VERSION = 1
WRAP_LOCAL = 1
WRAP_KMS = 2
_HEADER = struct.Struct(">2sBBH")
_NONCE = 12
_LOCAL_WRAP_AAD = b"copio-connector-dek-v1"
KMS_CONTEXT_PURPOSE = "connector-credential"


class VaultError(Exception):
    """A credential could not be sealed or opened. The message never holds secret material."""


class VaultMisconfigured(VaultError):
    pass


@dataclass(frozen=True)
class Secret:
    """A decrypted credential. Keep it in memory only; its repr hides the values."""

    access_token: str = field(repr=False)
    extra: Mapping[str, str] = field(default_factory=dict, repr=False)


class KmsClient(Protocol):
    """The two boto3 KMS calls the vault uses (a boto3 `kms` client satisfies this)."""

    def generate_data_key(self, **kwargs: Any) -> dict[str, Any]: ...
    def decrypt(self, **kwargs: Any) -> dict[str, Any]: ...


class KeyWrapper(Protocol):
    kind: int
    key_id: str

    def new_data_key(self, connection_id: uuid.UUID) -> tuple[bytes, bytes]:
        """(plaintext data key, wrapped data key)."""
        ...

    def unwrap(self, wrapped: bytes, connection_id: uuid.UUID) -> bytes: ...


class LocalKeyWrapper:
    """Dev and test only: the data key is wrapped with AES-256-GCM under a local key."""

    kind = WRAP_LOCAL

    def __init__(self, kek: bytes) -> None:
        if len(kek) != 32:
            raise VaultMisconfigured("CONNECTOR_LOCAL_KEK must be base64 of exactly 32 bytes")
        self._kek = AESGCM(kek)
        self.key_id = "local:" + hashlib.sha256(kek).hexdigest()[:16]

    def new_data_key(self, connection_id: uuid.UUID) -> tuple[bytes, bytes]:
        dek = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(_NONCE)
        return dek, nonce + self._kek.encrypt(nonce, dek, _LOCAL_WRAP_AAD)

    def unwrap(self, wrapped: bytes, connection_id: uuid.UUID) -> bytes:
        try:
            return self._kek.decrypt(wrapped[:_NONCE], wrapped[_NONCE:], _LOCAL_WRAP_AAD)
        except InvalidTag as exc:
            raise VaultError("data key could not be unwrapped with the local key") from exc


class KmsKeyWrapper:
    """The data key comes from KMS GenerateDataKey and is bound to the connection by encryption context."""

    kind = WRAP_KMS

    def __init__(self, client: KmsClient, key_id: str) -> None:
        self._client = client
        self.key_id = "kms:" + key_id
        self._kms_key_id = key_id

    @staticmethod
    def _context(connection_id: uuid.UUID) -> dict[str, str]:
        return {"purpose": KMS_CONTEXT_PURPOSE, "connection_id": str(connection_id)}

    def new_data_key(self, connection_id: uuid.UUID) -> tuple[bytes, bytes]:
        out = self._client.generate_data_key(KeyId=self._kms_key_id, KeySpec="AES_256",
                                             EncryptionContext=self._context(connection_id))
        return bytes(out["Plaintext"]), bytes(out["CiphertextBlob"])

    def unwrap(self, wrapped: bytes, connection_id: uuid.UUID) -> bytes:
        try:
            out = self._client.decrypt(CiphertextBlob=wrapped, KeyId=self._kms_key_id,
                                       EncryptionContext=self._context(connection_id))
        except Exception as exc:  # botocore errors; their text names the key, never the plaintext
            raise VaultError(f"KMS could not unwrap the data key ({type(exc).__name__})") from None
        return bytes(out["Plaintext"])


def _aad(header: bytes, connection_id: uuid.UUID) -> bytes:
    return header + connection_id.bytes


class Vault:
    def __init__(self, wrapper: KeyWrapper) -> None:
        self.wrapper = wrapper

    @property
    def key_id(self) -> str:
        return self.wrapper.key_id

    def seal(self, connection_id: uuid.UUID, secret: Secret) -> bytes:
        plaintext = json.dumps({"access_token": secret.access_token, "extra": dict(secret.extra)},
                               separators=(",", ":"), sort_keys=True).encode()
        dek, wdk = self.wrapper.new_data_key(connection_id)
        header = _HEADER.pack(MAGIC, FORMAT_VERSION, self.wrapper.kind, len(wdk)) + wdk
        nonce = os.urandom(_NONCE)
        body = AESGCM(dek).encrypt(nonce, plaintext, _aad(header, connection_id))
        return header + nonce + body

    def open(self, connection_id: uuid.UUID, blob: bytes) -> Secret:
        if len(blob) < _HEADER.size:
            raise VaultError("ciphertext is truncated")
        magic, version, kind, wdk_len = _HEADER.unpack_from(blob)
        if magic != MAGIC or version != FORMAT_VERSION:
            raise VaultError("unknown ciphertext format")
        if kind != self.wrapper.kind:
            raise VaultError("ciphertext was wrapped by a different kind of key")
        end = _HEADER.size + wdk_len
        if len(blob) < end + _NONCE + 16:
            raise VaultError("ciphertext is truncated")
        header, wdk = blob[:end], blob[_HEADER.size:end]
        nonce, body = blob[end:end + _NONCE], blob[end + _NONCE:]
        dek = self.wrapper.unwrap(wdk, connection_id)
        try:
            plaintext = AESGCM(dek).decrypt(nonce, body, _aad(header, connection_id))
        except InvalidTag as exc:
            raise VaultError("ciphertext failed authentication") from exc
        data = json.loads(plaintext)
        return Secret(access_token=str(data["access_token"]),
                      extra={str(k): str(v) for k, v in dict(data.get("extra") or {}).items()})


def vault_from_env(env: Mapping[str, str], kms_client: KmsClient | None = None) -> Vault:
    """KMS when CONNECTOR_KMS_KEY_ID is set, else the local key. The local key is refused when
    APP_ENV=production."""
    kms_key_id = env.get("CONNECTOR_KMS_KEY_ID", "").strip()
    if kms_key_id:
        if kms_client is None:
            import boto3  # only needed when KMS is configured

            kms_client = boto3.client("kms")
        return Vault(KmsKeyWrapper(kms_client, kms_key_id))
    local = env.get("CONNECTOR_LOCAL_KEK", "").strip()
    if env.get("APP_ENV", "").strip() == "production":
        raise VaultMisconfigured("APP_ENV=production needs CONNECTOR_KMS_KEY_ID; "
                                 "CONNECTOR_LOCAL_KEK is for dev and test only")
    if not local:
        raise VaultMisconfigured("set CONNECTOR_KMS_KEY_ID, or CONNECTOR_LOCAL_KEK for dev and test")
    try:
        kek = base64.b64decode(local, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VaultMisconfigured("CONNECTOR_LOCAL_KEK must be base64 of exactly 32 bytes") from exc
    return Vault(LocalKeyWrapper(kek))
# --- shared format end ---


class CredentialNotFound(Exception):
    """No credential row for this connection."""


def _lock_key(connection_id: uuid.UUID) -> int:
    """A signed 64-bit advisory lock key per connection (namespaced so other locks don't collide)."""
    digest = hashlib.sha256(b"copio.credentials:" + connection_id.bytes).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _lock(conn: Connection, connection_id: uuid.UUID) -> None:
    conn.execute(text("select pg_advisory_xact_lock(:k)"), {"k": _lock_key(connection_id)})


_REASON_MAX = 200
_SELECT = ("select cr.ciphertext, cr.version, cr.expires_at, cr.revoked_at, c.state"
           " from credentials cr join connections c on c.id = cr.connection_id"
           " where cr.connection_id = :id")
_SELECT_FOR_UPDATE = _SELECT + " for update of cr"


class PgCredentialStore(CredentialStore):
    def __init__(self, engine: Engine, vault: Vault) -> None:
        self.engine = engine
        self.vault = vault

    @classmethod
    def from_env(cls, engine: Engine, env: Mapping[str, str] | None = None) -> PgCredentialStore:
        """Refuses CONNECTOR_LOCAL_KEK when APP_ENV=production (raises VaultMisconfigured)."""
        return cls(engine, vault_from_env(os.environ if env is None else env))

    def _read(self, conn: Connection, connection_id: uuid.UUID, *, for_update: bool) -> Credential:
        sql = _SELECT_FOR_UPDATE if for_update else _SELECT
        row = conn.execute(text(sql), {"id": connection_id}).one_or_none()
        if row is None:
            raise CredentialNotFound(str(connection_id))
        if row.revoked_at is not None or row.state in ("reconnect_needed", "disconnected"):
            raise AuthRevoked("the connection needs to be reconnected")
        secret = self.vault.open(connection_id, bytes(row.ciphertext))
        return Credential(connection_id=connection_id, access_token=secret.access_token,
                          version=int(row.version), expires_at=row.expires_at, extra=dict(secret.extra))

    def get(self, connection_id: uuid.UUID) -> Credential:
        with self.engine.connect() as conn:
            return self._read(conn, connection_id, for_update=False)

    def _save(self, conn: Connection, current: Credential, access_token: str, expires_at: datetime | None,
              extra: Mapping[str, str] | None) -> Credential:
        """Write a new version over `current`, which the caller has read under the lock."""
        new_extra = dict(current.extra if extra is None else extra)
        blob = self.vault.seal(current.connection_id, Secret(access_token=access_token, extra=new_extra))
        version = conn.execute(text(
            "update credentials set ciphertext = :blob, key_id = :key_id, version = version + 1,"
            " expires_at = :expires_at, refreshed_at = now(), updated_at = now()"
            " where connection_id = :id and version = :version returning version"),
            {"blob": blob, "key_id": self.vault.key_id, "expires_at": expires_at,
             "id": current.connection_id, "version": current.version}).scalar_one()
        return Credential(connection_id=current.connection_id, access_token=access_token,
                          version=int(version), expires_at=expires_at, extra=new_extra)

    def rotate(self, cred: Credential, access_token: str, expires_at: datetime | None,
               extra: Mapping[str, str] | None = None) -> Credential:
        with self.engine.begin() as conn:
            _lock(conn, cred.connection_id)
            current = self._read(conn, cred.connection_id, for_update=True)
            if current.version != cred.version:
                return current  # lost the race: the winner's token stands, nothing is written
            return self._save(conn, current, access_token, expires_at, extra)

    def refresh(self, cred: Credential, refresher: TokenRefresher) -> Credential:
        """Refresh under the per-connection lock, so the provider is called at most once per version.

        If `cred.version` is still current, `refresher.refresh_token` is called exactly once and its
        result saved as version + 1. If another worker refreshed first, its credential comes back and the
        provider is not called. The lock is a transaction lock, held across the provider call: a second
        worker waits instead of spending a refresh token the first one is about to replace. Any error from
        the provider (AuthRevoked included) propagates and nothing is written; on AuthRevoked the caller
        then calls `mark_revoked`."""
        with self.engine.begin() as conn:
            _lock(conn, cred.connection_id)
            current = self._read(conn, cred.connection_id, for_update=True)
            if current.version != cred.version:
                return current
            access_token, expires_at = refresher.refresh_token(current)
            return self._save(conn, current, access_token, expires_at, None)

    def mark_revoked(self, connection_id: uuid.UUID, reason: str) -> None:
        """The connection moves to reconnect_needed (unless it was disconnected) and a system audit event
        is written, once per change. `reason` is shown to operators: pass a sanitized code or sentence."""
        reason = reason[:_REASON_MAX]
        with self.engine.begin() as conn:
            _lock(conn, connection_id)
            row = conn.execute(text("select workspace_id, state from connections where id = :id for update"),
                               {"id": connection_id}).one_or_none()
            if row is None:
                raise CredentialNotFound(str(connection_id))
            conn.execute(text("update credentials set revoked_at = coalesce(revoked_at, now()),"
                              " updated_at = now() where connection_id = :id"), {"id": connection_id})
            if row.state in ("reconnect_needed", "disconnected"):
                return
            conn.execute(text("update connections set state = 'reconnect_needed', state_reason = :reason,"
                              " updated_at = now() where id = :id"), {"id": connection_id, "reason": reason})
            conn.execute(text(
                "insert into audit_events (workspace_id, actor_type, actor_id, action, target_type,"
                " target_id, detail) values (:ws, 'system', 'credential-store', 'connection.auth_revoked',"
                " 'connection', :target, cast(:detail as jsonb))"),
                {"ws": row.workspace_id, "target": str(connection_id),
                 "detail": json.dumps({"from_state": row.state, "reason": reason})})


def connection_state(engine: Engine, connection_id: uuid.UUID) -> ConnectionState:
    """The connection's current state, for the runner. A connection that no longer exists reads as
    DISCONNECTED, so its runs stop instead of erroring."""
    with engine.connect() as conn:
        state = conn.execute(text("select state from connections where id = :id"),
                             {"id": connection_id}).scalar_one_or_none()
    return ConnectionState.DISCONNECTED if state is None else ConnectionState(state)
