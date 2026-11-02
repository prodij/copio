import json
import pathlib
from unittest.mock import MagicMock

import pytest

import aws_state


def test_frontend_values_are_public_https_urls_and_ids() -> None:
    assert aws_state.frontend_values("x.test", "c1", "p1") == {
        "VITE_API_BASE_URL": "https://api.x.test",
        "ZITADEL_ISSUER": "https://auth.x.test",
        "ZITADEL_CLIENT_ID": "c1",
        "ZITADEL_PROJECT_ID": "p1",
    }


def test_publish_frontend_writes_the_parameter() -> None:
    ssm = MagicMock()
    aws_state.publish_frontend(ssm, "acme", {"A": "1"})
    ssm.put_parameter.assert_called_once_with(
        Name="/acme/frontend", Value=json.dumps({"A": "1"}), Type="String", Overwrite=True)


def state_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "zitadel").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "zitadel/admin.pat").write_text("A\n")
    (tmp_path / "zitadel/login-client.pat").write_text("L\n")
    (tmp_path / "backend/backend.pat").write_text("B\n")
    (tmp_path / "ids.env").write_text("X=1\n")
    return tmp_path


def test_save_tokens_stores_all_four(tmp_path: pathlib.Path) -> None:
    secrets = MagicMock()
    aws_state.save_tokens(secrets, "acme", state_dir(tmp_path))
    call = secrets.put_secret_value.call_args.kwargs
    assert call["SecretId"] == "acme/bootstrap"
    assert json.loads(call["SecretString"]) == {
        "admin_pat": "A", "login_client_pat": "L", "backend_pat": "B", "ids_env": "X=1\n"}


def test_save_tokens_refuses_a_partial_set(tmp_path: pathlib.Path) -> None:
    root = state_dir(tmp_path)
    (root / "backend/backend.pat").unlink()
    secrets = MagicMock()
    with pytest.raises(SystemExit, match=r"backend\.pat"):
        aws_state.save_tokens(secrets, "acme", root)
    secrets.put_secret_value.assert_not_called()
