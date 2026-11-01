import pytest
from pydantic import ValidationError

from app.config import Settings
from tests.conftest import TEST_SETTINGS


def test_live_stripe_key_is_rejected() -> None:
    data = TEST_SETTINGS.model_dump() | {"stripe_secret_key": "sk_live_x"}
    with pytest.raises(ValidationError, match="test-mode"):
        Settings(**data)


def test_importing_app_main_needs_no_env() -> None:
    import importlib

    import app.main

    importlib.reload(app.main)
