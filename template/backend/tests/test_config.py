import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import Settings
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
