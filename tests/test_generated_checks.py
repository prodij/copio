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


def product_copy(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    product = tmp_path / "product"
    shutil.copytree(product_dir, product, ignore=shutil.ignore_patterns("node_modules", ".venv"))
    return product


@pytest.mark.slow
def test_a_product_can_change_its_plans(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Plans are the product's to edit: rename the starter plan, list another first, add seats."""
    product = product_copy(product_dir, tmp_path)
    plans = product / "backend" / "app" / "billing" / "plans.yaml"
    text = plans.read_text().replace("seats: 5", "seats: 6").replace("name: Starter", "name: Base")
    extra = "  - {code: first, name: First, amount_cents: 100, currency: USD, interval: month, features: {seats: 1}}\n"
    plans.write_text(text.replace("plans:\n", "plans:\n" + extra))
    env = {**os.environ, "TEST_DATABASE_URL": os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://app:app@127.0.0.1:5432/app_test")}
    result = subprocess.run(["uv", "run", "pytest", "-q"], cwd=product / "backend", env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, (result.stdout + result.stderr)[-6000:]
    spec = (product / "e2e" / "signup-to-premium.spec.ts").read_text()
    assert "Choose Starter" not in spec, "the e2e buys the plan by its code, whatever it is called"


def make(product: pathlib.Path, target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["make", target], cwd=product, capture_output=True, text=True, check=False)


def tree_state(product: pathlib.Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for folder in ("frontend/src", "frontend/public", "backend")
            for p in (product / folder).rglob("*") if p.is_file() and ".venv" not in p.parts and "__pycache__" not in p.parts}


@pytest.mark.slow
@pytest.mark.parametrize(
    ("stale", "said"),
    [
        ("frontend/src/brand.css", "frontend/src/brand.css"),
        ("frontend/public/logo.svg", "frontend/public/logo.svg"),
        ("backend/openapi.json", "backend/openapi.json"),
        ("frontend/src/api/schema.d.ts", "frontend/src/api/schema.d.ts"),
    ],
)
def test_make_check_catches_generated_drift_and_regen_fixes_it(
    product_dir: pathlib.Path, tmp_path: pathlib.Path, stale: str, said: str
) -> None:
    product = product_copy(product_dir, tmp_path)
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=product / "frontend", check=True, capture_output=True)
    fresh = make(product, "check-generated")
    assert fresh.returncode == 0, (fresh.stdout + fresh.stderr)[-2000:]
    target = product / stale
    target.write_text(target.read_text() + "\n/* old */\n" if stale.endswith(("css", "svg", "ts")) else "{}\n")
    before = tree_state(product)
    result = make(product, "check-generated")
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert said in output and "make regen" in output
    assert tree_state(product) == before, "the check must not change the tree"
    regen = make(product, "regen")
    assert regen.returncode == 0, (regen.stdout + regen.stderr)[-2000:]
    again = make(product, "check-generated")
    assert again.returncode == 0, (again.stdout + again.stderr)[-2000:]


@pytest.mark.slow
def test_regen_leaves_an_in_step_lock_alone_and_relocks_a_changed_one(
    product_dir: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    product = product_copy(product_dir, tmp_path)
    locks = [product / "frontend" / "package-lock.json", product / "e2e" / "package-lock.json"]
    before = [lock.read_bytes() for lock in locks]
    regen = make(product, "regen")
    assert regen.returncode == 0, (regen.stdout + regen.stderr)[-2000:]
    assert [lock.read_bytes() for lock in locks] == before, "a fresh product's first make regen must not dirty git"

    package = product / "frontend" / "package.json"
    package.write_text(package.read_text().replace('"dependencies": {', '"dependencies": {\n    "clsx": "2.1.1",', 1))
    regen = make(product, "regen")
    assert regen.returncode == 0, (regen.stdout + regen.stderr)[-2000:]
    assert "node_modules/clsx" in locks[0].read_text()
