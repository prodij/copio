import os
import pathlib
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import BillingModeSettings, DatabaseSettings, Settings
from tests.conftest import TEST_SETTINGS


def test_live_stripe_key_is_rejected() -> None:
    data = TEST_SETTINGS.model_dump() | {"stripe_secret_key": "sk_live_x"}
    with pytest.raises(ValidationError, match="test-mode"):
        Settings(**data)


@pytest.mark.parametrize("key", ["", " "])
def test_stripe_key_may_be_empty(key: str) -> None:
    settings = Settings(**(TEST_SETTINGS.model_dump() | {"stripe_secret_key": key}))
    assert settings.stripe_secret_key == ""
    assert not settings.stripe_configured
    assert TEST_SETTINGS.stripe_configured


def test_stripe_key_may_be_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    data = TEST_SETTINGS.model_dump()
    del data["stripe_secret_key"]
    assert Settings(**data).stripe_secret_key == ""


@pytest.mark.parametrize("key", ["rk_test_x", "pk_test_x", "whatever"])
def test_any_other_stripe_key_is_rejected(key: str) -> None:
    with pytest.raises(ValidationError, match="test-mode"):
        Settings(**(TEST_SETTINGS.model_dump() | {"stripe_secret_key": key}))


def test_importing_app_main_needs_no_env() -> None:
    env = {k: v for k, v in os.environ.items() if k.lower() not in Settings.model_fields}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_service_token_is_read_from_file(tmp_path: pathlib.Path) -> None:
    token_file = tmp_path / "backend.pat"
    token_file.write_text("pat-from-file\n")
    data = TEST_SETTINGS.model_dump() | {"zitadel_service_token": "", "zitadel_service_token_file": str(token_file)}
    assert Settings(**data).zitadel_service_token == "pat-from-file"


def test_explicit_service_token_wins_over_file(tmp_path: pathlib.Path) -> None:
    data = TEST_SETTINGS.model_dump() | {"zitadel_service_token_file": str(tmp_path / "missing.pat")}
    assert Settings(**data).zitadel_service_token == TEST_SETTINGS.zitadel_service_token


def test_missing_service_token_file_is_clear(tmp_path: pathlib.Path) -> None:
    data = TEST_SETTINGS.model_dump() | {"zitadel_service_token": "", "zitadel_service_token_file": str(tmp_path / "missing.pat")}
    with pytest.raises(ValidationError, match="make bootstrap"):
        Settings(**data)


def test_migrations_need_only_the_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/x")
    assert DatabaseSettings().database_url == "postgresql+psycopg://u:p@db/x"


MOCK = TEST_SETTINGS.model_dump() | {"stripe_secret_key": "", "billing_mode": "mock", "app_env": "local"}


def test_mock_payment_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BILLING_MODE", "APP_ENV", "STRIPE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert not BillingModeSettings().mock_payment
    data = {k: v for k, v in MOCK.items() if k not in ("billing_mode", "app_env")}
    settings = Settings(**data)
    assert not settings.mock_payment and not settings.billing_configured


def test_mock_payment_turns_on_only_when_local_with_no_key() -> None:
    settings = Settings(**MOCK)
    assert settings.mock_payment and settings.billing_configured and not settings.stripe_configured


@pytest.mark.parametrize("app_env", ["", "production", "staging", "LOCAL", "local-ish"])
def test_mock_payment_is_refused_unless_explicitly_local(app_env: str) -> None:
    with pytest.raises(ValidationError, match="needs APP_ENV=local"):
        Settings(**(MOCK | {"app_env": app_env}))


def test_mock_payment_is_refused_with_a_stripe_key() -> None:
    with pytest.raises(ValidationError, match="STRIPE_SECRET_KEY is set"):
        Settings(**(MOCK | {"stripe_secret_key": "sk_test_x"}))


@pytest.mark.parametrize("mode", ["MOCK", "fake", "test", "stripe"])
def test_any_other_billing_mode_is_refused(mode: str) -> None:
    with pytest.raises(ValidationError, match="must be empty or mock"):
        Settings(**(MOCK | {"billing_mode": mode}))


@pytest.mark.parametrize(("env", "message"), [
    ({"BILLING_MODE": "mock"}, "needs APP_ENV=local"),
    ({"BILLING_MODE": "mock", "APP_ENV": "production"}, "needs APP_ENV=local"),
    ({"BILLING_MODE": "mock", "APP_ENV": "local", "STRIPE_SECRET_KEY": "sk_test_x"}, "STRIPE_SECRET_KEY is set"),
])
def test_the_backend_refuses_to_start_on_unsafe_mock_payment(env: dict[str, str], message: str) -> None:
    clean = {k: v for k, v in os.environ.items() if k.lower() not in Settings.model_fields}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"], env=clean | env, capture_output=True, text=True
    )
    assert result.returncode != 0 and message in result.stderr


def test_a_refusal_never_prints_the_stripe_key() -> None:
    clean = {k: v for k, v in os.environ.items() if k.lower() not in Settings.model_fields}
    env = {"BILLING_MODE": "mock", "APP_ENV": "local", "STRIPE_SECRET_KEY": "sk_test_tail-of-the-key"}
    result = subprocess.run([sys.executable, "-c", "import app.main"], env=clean | env, capture_output=True, text=True)
    assert "is set" in result.stderr and "tail-of-the-key" not in result.stderr
    with pytest.raises(ValidationError) as refused:
        Settings(**(TEST_SETTINGS.model_dump() | {"stripe_secret_key": "sk_live_tail-of-the-key"}))
    assert "tail-of-the-key" not in str(refused.value)


def test_the_backend_starts_with_mock_payment_when_it_is_safe() -> None:
    clean = {k: v for k, v in os.environ.items() if k.lower() not in Settings.model_fields}
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"], env=clean | {"BILLING_MODE": "mock", "APP_ENV": "local"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
