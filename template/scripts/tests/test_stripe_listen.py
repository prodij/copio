import os
import pathlib
import subprocess

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "stripe-listen.sh"


def run(tmp_path: pathlib.Path, **env: str) -> subprocess.CompletedProcess[str]:
    """Run the stripe-cli entrypoint with a fake `stripe` that prints its arguments."""
    fake = tmp_path / "stripe"
    fake.write_text('#!/bin/sh\necho "stripe $*"\n')
    fake.chmod(0o755)
    return subprocess.run(
        ["/bin/sh", str(SCRIPT)], capture_output=True, text=True, check=False,
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}", **env},
    )


@pytest.mark.parametrize("key", ["sk_live_x", "rk_live_x", "pk_test_x", "whatever"])
def test_refuses_anything_but_a_test_key(tmp_path: pathlib.Path, key: str) -> None:
    result = run(tmp_path, STRIPE_API_KEY=key, LAGO_ORGANIZATION_ID="o1")
    assert result.returncode == 1
    assert "only Stripe test keys" in result.stderr
    assert "stripe listen" not in result.stdout


@pytest.mark.parametrize("env", [{}, {"STRIPE_API_KEY": "sk_test_x"}])
def test_idles_until_key_and_bootstrap(tmp_path: pathlib.Path, env: dict[str, str]) -> None:
    result = run(tmp_path, **env)
    assert result.returncode == 0
    assert "idle until" in result.stdout


@pytest.mark.parametrize("key", ["sk_test_x", "rk_test_x"])
def test_forwards_to_lagos_stripe_route(tmp_path: pathlib.Path, key: str) -> None:
    result = run(tmp_path, STRIPE_API_KEY=key, LAGO_ORGANIZATION_ID="o1")
    assert result.stdout.strip() == (
        "stripe listen --forward-to http://lago-api:3000/webhooks/stripe/o1?code=stripe")
