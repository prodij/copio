import os
import pathlib
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import DatabaseSettings, Settings
from tests.conftest import TEST_SETTINGS


def test_live_stripe_key_is_rejected() -> None:
    data = TEST_SETTINGS.model_dump() | {"stripe_secret_key": "sk_live_x"}
    with pytest.raises(ValidationError, match="test-mode"):
        Settings(**data)


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
