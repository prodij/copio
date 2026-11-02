import base64
import pathlib
from unittest.mock import MagicMock

import pytest

import infra


def test_read_tfvars(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "terraform.tfvars"
    path.write_text('# note\nslug = "acme"\naws_account_id   = "123"\nadmin_cidrs = []\n')
    assert infra.read_tfvars(path) == {"slug": "acme", "aws_account_id": "123"}


def test_wrong_account_is_refused() -> None:
    infra.check_account("123", "123")
    with pytest.raises(SystemExit, match=r"999.*123"):
        infra.check_account("999", "123")


def test_placeholder_account_is_refused() -> None:
    with pytest.raises(SystemExit, match=r"terraform\.tfvars"):
        infra.check_account("000000000000", "000000000000")


def test_filling_secrets_never_changes_an_existing_value() -> None:
    existing = {"ZITADEL_MASTERKEY": "keep-me", "LAGO_API_KEY": "keep-too"}
    filled = infra.fill_secrets(existing, lambda command: f"new:{command}")
    assert filled["ZITADEL_MASTERKEY"] == "keep-me"
    assert filled["LAGO_API_KEY"] == "keep-too"
    assert filled["SECRET_KEY_BASE"] == "new:openssl rand -hex 64"
    assert set(infra.SECRET_SPECS) <= set(filled)


def test_filling_twice_changes_nothing() -> None:
    once = infra.fill_secrets({}, lambda command: "x")
    assert infra.fill_secrets(once, lambda command: "y") == once


def test_smtp_password_has_the_documented_shape() -> None:
    password = infra.smtp_password("secret", "us-west-2")
    raw = base64.b64decode(password)
    assert raw[0] == 4 and len(raw) == 33
    assert password != infra.smtp_password("secret", "us-east-1")


@pytest.mark.parametrize("key", ["sk_live_abc", "rk_test_abc", "", "whatever"])
def test_only_stripe_test_keys_are_accepted(key: str) -> None:
    with pytest.raises(SystemExit):
        infra.check_stripe_key(key)


def test_stripe_test_key_is_accepted() -> None:
    assert infra.check_stripe_key(" sk_test_abc\n") == "sk_test_abc"


def test_destroy_deletes_the_parameters_terraform_does_not_own() -> None:
    ssm = MagicMock()
    infra.delete_parameters(ssm, "acme")
    ssm.delete_parameters.assert_called_once_with(
        Names=["/acme/tags/backend", "/acme/tags/jobs", "/acme/frontend"])


def test_bundle_skips_caches_and_virtualenvs(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "scripts" / ".ruff_cache").mkdir(parents=True)
    (tmp_path / "scripts" / ".venv").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("")
    (tmp_path / "scripts" / ".ruff_cache" / "x").write_text("")
    (tmp_path / "scripts" / ".venv" / "y").write_text("")
    (tmp_path / "docker-compose.aws.yml").write_text("")
    monkeypatch.setattr(infra, "ROOT", tmp_path)
    s3 = MagicMock()
    infra.upload_bundle(s3, "bucket")
    keys = sorted(call.args[2] for call in s3.upload_file.call_args_list)
    assert keys == ["current/docker-compose.aws.yml", "current/scripts/a.py"]
