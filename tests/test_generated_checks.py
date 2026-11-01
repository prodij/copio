import pathlib
import subprocess

import pytest


@pytest.mark.slow
def test_generated_product_passes_make_check(product_dir: pathlib.Path) -> None:
    """Lint, typecheck and every unit test of a freshly generated product (needs Postgres: the
    product's Makefile reads TEST_DATABASE_URL, default 127.0.0.1:5432/app_test)."""
    result = subprocess.run(["make", "check"], cwd=product_dir, capture_output=True, text=True, check=False)
    assert result.returncode == 0, (result.stdout + result.stderr)[-6000:]
