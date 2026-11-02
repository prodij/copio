import base64
import pathlib
import re

import pytest

import make_env

EXAMPLE = """# Stripe key: paste it
STRIPE_SECRET_KEY=

# Default: 8085
ZITADEL_PORT=
# Exactly 32 characters
# Generate: openssl rand -hex 16
ZITADEL_MASTERKEY=
# Generate: openssl rand -base64 32
COOKIE_SECRET=
"""


def test_fills_defaults_and_generated_values_but_not_stripe(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".env.example").write_text(EXAMPLE)
    make_env.main(tmp_path)
    values = make_env.read_env(tmp_path / ".env")
    assert values["STRIPE_SECRET_KEY"] == ""
    assert values["ZITADEL_PORT"] == "8085"
    assert len(values["ZITADEL_MASTERKEY"]) == 32
    assert len(values["COOKIE_SECRET"]) == 44
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600


def test_keeps_existing_values_and_extra_keys(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".env.example").write_text(EXAMPLE)
    (tmp_path / ".env").write_text("STRIPE_SECRET_KEY=sk_test_x\nZITADEL_MASTERKEY=keep\nMY_VAR=1\n")
    make_env.main(tmp_path)
    values = make_env.read_env(tmp_path / ".env")
    assert values["STRIPE_SECRET_KEY"] == "sk_test_x"
    assert values["ZITADEL_MASTERKEY"] == "keep"
    assert values["MY_VAR"] == "1"


def test_a_marker_applies_only_to_the_key_right_below_its_comment_block() -> None:
    text, missing = make_env.render("# Default: 1\nA=\n\nB=\n", {})
    assert text == "# Default: 1\nA=1\n\nB=\n"
    assert missing == ["B"]


def test_reports_what_is_still_empty(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".env.example").write_text(EXAMPLE)
    make_env.main(tmp_path)
    assert "fill these in .env: STRIPE_SECRET_KEY" in capsys.readouterr().out


def test_rsa_key_is_base64_pem() -> None:
    assert base64.b64decode(make_env.generate("openssl genrsa 2048 | openssl base64 -A")).startswith(b"-----BEGIN")


def test_unknown_generator_is_an_error() -> None:
    with pytest.raises(SystemExit, match="unknown generator"):
        make_env.generate("openssl rand -hex sixteen")


def test_password_meets_zitadels_default_policy() -> None:
    for _ in range(50):
        value = make_env.generate("password 24")
        assert len(value) == 24
        assert re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"[0-9]", value)
        assert re.fullmatch(r"[A-Za-z0-9-]+", value) and "-" in value


def test_mock_payment_stays_off_and_is_not_reported_as_missing() -> None:
    text, missing = make_env.render("BILLING_MODE=\nAPP_ENV=\nSTRIPE_SECRET_KEY=\n", {})
    assert text == "BILLING_MODE=\nAPP_ENV=\nSTRIPE_SECRET_KEY=\n"
    assert missing == ["STRIPE_SECRET_KEY"]


def test_mock_payment_set_in_env_is_kept() -> None:
    text, _ = make_env.render("BILLING_MODE=\nAPP_ENV=\n", {"BILLING_MODE": "mock", "APP_ENV": "local"})
    assert text == "BILLING_MODE=mock\nAPP_ENV=local\n"
