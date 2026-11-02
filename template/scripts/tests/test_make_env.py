import base64
import pathlib
import re
import socket

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


@pytest.fixture(autouse=True)
def every_port_is_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """So these tests don't depend on what runs on this machine, like this product's own stack."""
    monkeypatch.setattr(make_env, "port_free", lambda port: True)


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


PORTS = "# Default: 5173\nAPP_PORT=\n# Default: 8000\nAPI_PORT=\n# Default: 7\nNOT_A_PORT_VALUE=\n"


def test_a_taken_default_moves_all_the_ports_together(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(make_env, "port_free", lambda port: port not in (8000, 5183))
    text, _ = make_env.render(PORTS, {})
    # 8000 is taken, so +10; 5183 is taken, so +20. Everything moves by the same step.
    assert "APP_PORT=5193\nAPI_PORT=8020\n" in text
    assert "NOT_A_PORT_VALUE=7\n" in text
    assert "moved up by 20: APP_PORT=5193, API_PORT=8020" in capsys.readouterr().out


def test_free_defaults_stay_and_say_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    text, _ = make_env.render(PORTS, {})
    assert "APP_PORT=5173\nAPI_PORT=8000\n" in text
    assert capsys.readouterr().out == ""


def test_ports_already_in_env_are_kept_and_not_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    def probe(port: int) -> bool:
        raise AssertionError(f"probed {port}")

    monkeypatch.setattr(make_env, "port_free", probe)
    text, _ = make_env.render(PORTS.replace("# Default: 7\nNOT_A_PORT_VALUE=\n", ""), {"APP_PORT": "5173", "API_PORT": "9"})
    assert "APP_PORT=5173\nAPI_PORT=9\n" in text


def test_a_blanked_port_is_picked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(make_env, "port_free", lambda port: port != 8000)
    text, _ = make_env.render(PORTS, {"APP_PORT": "", "API_PORT": ""})
    assert "APP_PORT=5183\nAPI_PORT=8010\n" in text


def test_port_free_sees_a_real_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the real check
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert make_env.port_free(port) is False
    assert make_env.port_free(port) is True


def test_no_free_block_says_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(make_env, "port_free", lambda port: False)
    with pytest.raises(SystemExit, match="by hand"):
        make_env.render(PORTS, {})
