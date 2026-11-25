"""Envelope encryption for connector credentials.

Every credential gets a fresh 256-bit data key. The data key encrypts the credential with AES-256-GCM,
and is itself wrapped by AWS KMS (`CONNECTOR_KMS_KEY_ID`) or, in dev and test only, by a local
key-encryption key (`CONNECTOR_LOCAL_KEK`, base64 of 32 bytes). The jobs worker decrypts the same bytes
with jobs/jobs/sync/credentials.py, which carries an identical copy of the format code below; a shared
test vector in both test suites proves the two agree. Change one, change both.

Ciphertext format, version 1 (all integers big-endian):

    magic   b"CV"            2 bytes
    version 0x01             1 byte
    wrapper 0x01 local | 0x02 kms
    wdk_len                  2 bytes
    wdk                      wdk_len bytes (local: 12-byte nonce + GCM(kek, dek); kms: CiphertextBlob)
    nonce                    12 bytes
    body                     AES-256-GCM(dek, nonce, plaintext, aad) including the 16-byte tag

`aad` is the header (everything before `nonce`) followed by the connection id's 16 bytes, so a
ciphertext cannot be moved to another connection or have its header edited. The plaintext is UTF-8
JSON: {"access_token": str, "extra": {str: str}}.

Nothing here logs, and no exception message carries plaintext or key material.
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
from functools import lru_cache
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- shared format begin (identical in jobs/jobs/sync/credentials.py) ---
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


@lru_cache(maxsize=4)
def _cached_vault(kms_key_id: str, local_kek: str, app_env: str) -> Vault:
    return vault_from_env({"CONNECTOR_KMS_KEY_ID": kms_key_id, "CONNECTOR_LOCAL_KEK": local_kek,
                           "APP_ENV": app_env})


def get_vault() -> Vault:
    """FastAPI dependency, read from the environment on first use. A misconfigured vault fails the
    connector routes with a clear error and leaves the rest of the app running."""
    return _cached_vault(*(os.environ.get(name, "") for name in
                           ("CONNECTOR_KMS_KEY_ID", "CONNECTOR_LOCAL_KEK", "APP_ENV")))
