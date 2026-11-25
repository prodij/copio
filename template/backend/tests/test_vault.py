"""The backend's envelope encryption, and the ciphertext format it shares with the jobs worker."""

import base64
import os
import uuid
from typing import Any

import pytest

from app.connectors import vault as vault_module
from app.connectors.vault import (
    KmsKeyWrapper,
    Secret,
    Vault,
    VaultError,
    VaultMisconfigured,
    get_vault,
    vault_from_env,
)

# ---- Shared test vector: the same constants are in jobs/tests/test_credentials.py. Both sides must open
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


class FakeKms:
    """KMS GenerateDataKey/Decrypt in memory, with encryption-context checking like the real service."""

    def __init__(self) -> None:
        self.keys: dict[bytes, tuple[bytes, dict[str, str]]] = {
            VECTOR_KMS_BLOB: (VECTOR_KMS_DEK, {"purpose": "connector-credential",
                                               "connection_id": str(VECTOR_CONNECTION_ID)})}
        self.calls: list[dict[str, Any]] = []

    def generate_data_key(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        assert kwargs["KeySpec"] == "AES_256"
        dek, blob = os.urandom(32), b"fake-kms:" + os.urandom(16)
        self.keys[blob] = (dek, kwargs["EncryptionContext"])
        return {"Plaintext": dek, "CiphertextBlob": blob, "KeyId": kwargs["KeyId"]}

    def decrypt(self, **kwargs: Any) -> dict[str, Any]:
        dek, context = self.keys[kwargs["CiphertextBlob"]]
        if context != kwargs["EncryptionContext"]:
            raise RuntimeError("InvalidCiphertextException")
        return {"Plaintext": dek}


def local_vault() -> Vault:
    return vault_from_env({"CONNECTOR_LOCAL_KEK": VECTOR_KEK_B64})


def test_shared_vector_opens_with_the_local_key() -> None:
    secret = local_vault().open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_LOCAL_HEX))
    assert (secret.access_token, dict(secret.extra)) == (VECTOR_TOKEN, VECTOR_EXTRA)
    assert local_vault().key_id == "local:630dcd2966c43366"


def test_shared_vector_opens_with_kms() -> None:
    vault = Vault(KmsKeyWrapper(FakeKms(), "alias/synthetic"))
    secret = vault.open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_KMS_HEX))
    assert (secret.access_token, dict(secret.extra)) == (VECTOR_TOKEN, VECTOR_EXTRA)


def test_kms_round_trip_binds_the_connection() -> None:
    kms = FakeKms()
    vault = vault_from_env({"CONNECTOR_KMS_KEY_ID": "alias/synthetic", "APP_ENV": "production"},
                           kms_client=kms)
    cid = uuid.uuid4()
    blob = vault.seal(cid, Secret("synthetic-kms"))
    assert vault.key_id == "kms:alias/synthetic"
    assert kms.calls[0]["EncryptionContext"] == {"purpose": "connector-credential", "connection_id": str(cid)}
    assert vault.open(cid, blob).access_token == "synthetic-kms"
    with pytest.raises(VaultError) as info:
        vault.open(uuid.uuid4(), blob)
    assert "synthetic-kms" not in str(info.value)


def test_local_and_kms_ciphertexts_are_not_interchangeable() -> None:
    with pytest.raises(VaultError):
        local_vault().open(VECTOR_CONNECTION_ID, bytes.fromhex(VECTOR_KMS_HEX))


def test_tampering_is_refused() -> None:
    blob = bytearray(bytes.fromhex(VECTOR_LOCAL_HEX))
    blob[-1] ^= 1
    with pytest.raises(VaultError):
        local_vault().open(VECTOR_CONNECTION_ID, bytes(blob))
    with pytest.raises(VaultError):
        local_vault().open(VECTOR_CONNECTION_ID, b"XX\x01")


def test_secret_repr_hides_values() -> None:
    assert "synthetic" not in repr(Secret("synthetic-hidden", {"k": "synthetic-hidden-2"}))


def test_production_refuses_the_local_key() -> None:
    with pytest.raises(VaultMisconfigured) as info:
        vault_from_env({"CONNECTOR_LOCAL_KEK": VECTOR_KEK_B64, "APP_ENV": "production"})
    assert VECTOR_KEK_B64 not in str(info.value)


@pytest.mark.parametrize("value", ["", "%%%", base64.b64encode(b"too-short").decode()])
def test_a_missing_or_bad_local_key_is_refused(value: str) -> None:
    with pytest.raises(VaultMisconfigured) as info:
        vault_from_env({"CONNECTOR_LOCAL_KEK": value})
    assert not value or value not in str(info.value)


def test_get_vault_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    vault_module._cached_vault.cache_clear()
    monkeypatch.setenv("CONNECTOR_LOCAL_KEK", VECTOR_KEK_B64)
    monkeypatch.delenv("CONNECTOR_KMS_KEY_ID", raising=False)
    monkeypatch.setenv("APP_ENV", "local")
    assert get_vault() is get_vault()
    assert get_vault().key_id == "local:630dcd2966c43366"
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(VaultMisconfigured):
        get_vault()
    vault_module._cached_vault.cache_clear()
