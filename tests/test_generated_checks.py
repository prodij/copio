import os
import pathlib
import shutil
import subprocess

import pytest


@pytest.mark.slow
def test_generated_product_passes_make_check(product_dir: pathlib.Path) -> None:
    """Lint, typecheck and every unit test of a freshly generated product (needs Postgres: the
    product's Makefile reads TEST_DATABASE_URL, default 127.0.0.1:5432/app_test)."""
    result = subprocess.run(["make", "check"], cwd=product_dir, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (result.stdout + result.stderr)[-6000:]


@pytest.mark.slow
def test_a_product_can_change_its_plans(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Plans are the product's to edit, so its shipped tests must not pin the template's."""
    product = tmp_path / "product"
    shutil.copytree(product_dir, product, ignore=shutil.ignore_patterns("node_modules", ".venv"))
    plans = product / "backend" / "app" / "billing" / "plans.yaml"
    plans.write_text(plans.read_text().replace("seats: 5", "seats: 6") + (
        "  - {code: extra, name: Extra, amount_cents: 100, currency: USD, interval: month, features: {seats: 1}}\n"))
    env = {**os.environ, "TEST_DATABASE_URL": os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://app:app@127.0.0.1:5432/app_test")}
    result = subprocess.run(["uv", "run", "pytest", "-q"], cwd=product / "backend", env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, (result.stdout + result.stderr)[-6000:]
