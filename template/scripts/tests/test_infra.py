import base64
import pathlib
from unittest.mock import MagicMock

import pytest

import infra
import make_env


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


def test_bundle_skips_env_files_and_ds_store(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "deploy").mkdir()
    for name in ["Caddyfile", ".env", ".env.local", ".DS_Store", ".envrc-not"]:
        (tmp_path / "deploy" / name).write_text("")
    monkeypatch.setattr(infra, "ROOT", tmp_path)
    s3 = MagicMock()
    infra.upload_bundle(s3, "bucket")
    keys = sorted(call.args[2] for call in s3.upload_file.call_args_list)
    assert keys == ["current/deploy/.envrc-not", "current/deploy/Caddyfile"]


def test_release_refuses_a_dirty_tree() -> None:
    infra.check_clean("")
    infra.check_clean("\n")
    with pytest.raises(SystemExit, match="uncommitted"):
        infra.check_clean(" M backend/app/main.py\n")


def test_bootstrap_command_is_pinned() -> None:
    assert infra.BOOTSTRAP_COMMAND == (
        'export HOME="${HOME:-/root}" PATH="$PATH:/usr/local/bin"; app-start && /opt/app/deploy/first-run.sh')


@pytest.mark.parametrize("name", [n for n, c in infra.SECRET_SPECS.items() if "genrsa" not in c])
def test_every_secret_command_is_understood_by_make_env(name: str) -> None:
    assert make_env.generate(infra.SECRET_SPECS[name])


def test_init_finishes_an_existing_bucket(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    tfvars = {"slug": "acme", "aws_account_id": "123", "aws_region": "us-west-2"}
    s3 = MagicMock()
    s3.list_buckets.return_value = {"Buckets": [{"Name": "acme-tfstate-123"}]}
    aws = MagicMock()
    aws.client.return_value = s3
    monkeypatch.setattr(infra, "read_tfvars", lambda *a: tfvars)
    monkeypatch.setattr(infra, "session", lambda: aws)
    monkeypatch.setattr(infra, "INFRA", tmp_path)
    monkeypatch.setattr(infra.subprocess, "run", MagicMock())
    infra.init()
    s3.create_bucket.assert_not_called()
    s3.put_bucket_versioning.assert_called_once()
    s3.put_public_access_block.assert_called_once()


def test_bundle_skips_the_local_rehearsal(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "deploy" / "rehearsal").mkdir(parents=True)
    (tmp_path / "deploy" / "start.sh").write_text("x")
    (tmp_path / "deploy" / "rehearsal" / "rehearsal.env").write_text("x")
    monkeypatch.setattr(infra, "ROOT", tmp_path)
    monkeypatch.setattr(infra, "BUNDLE", ["deploy"])
    s3 = MagicMock()
    infra.upload_bundle(s3, "bucket")
    keys = [call.args[2] for call in s3.upload_file.call_args_list]
    assert keys == ["current/deploy/start.sh"]
