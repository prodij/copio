import pathlib
import re
import subprocess
import sys

import pytest
import yaml
from copier import run_copy

from conftest import ANSWERS, ROOT

SECRET_PATTERNS = [
    re.compile(r"sk_(live|test)_[0-9A-Za-z]{10,}"),
    re.compile(r"whsec_[0-9A-Za-z]{10,}"),
    re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def test_product_has_top_level_layout(product_dir: pathlib.Path) -> None:
    for name in ["backend", "frontend", "jobs", "infra", "brand", "README.md", ".gitignore"]:
        assert (product_dir / name).exists(), name


def test_answers_are_rendered(product_dir: pathlib.Path) -> None:
    readme = (product_dir / "README.md").read_text()
    assert "# Acme Reports" in readme
    assert "{{" not in readme


def test_env_is_ignored(product_dir: pathlib.Path) -> None:
    assert ".env" in (product_dir / ".gitignore").read_text().splitlines()


def test_no_secret_values_anywhere() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    offenders = []
    for rel in listing:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(text) for p in SECRET_PATTERNS):
            offenders.append(rel)
    assert offenders == []


def test_default_logo_is_the_template_logo(product_dir: pathlib.Path) -> None:
    assert "<svg" in (product_dir / "brand" / "logo.svg").read_text()
    assert (product_dir / "brand" / "brand.yaml").read_text().count("Acme Reports") == 1


def test_env_example_lists_names_only(product_dir: pathlib.Path) -> None:
    keys = [line for line in (product_dir / ".env.example").read_text().splitlines()
            if line and not line.startswith("#")]
    assert keys and all(re.fullmatch(r"[A-Z][A-Z0-9_]*=", line) for line in keys), keys


def test_local_state_is_ignored(product_dir: pathlib.Path) -> None:
    ignored = (product_dir / ".gitignore").read_text().splitlines()
    assert ".env" in ignored and ".bootstrap/" in ignored


def test_every_env_file_but_the_example_is_ignored(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text((product_dir / ".gitignore").read_text())
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    names = [".env", ".env.local", ".env.production", ".env.example"]
    result = subprocess.run(["git", "check-ignore", *names], cwd=repo, capture_output=True, text=True, check=False)
    assert result.stdout.split() == [".env", ".env.local", ".env.production"]


def test_template_env_example_is_not_hidden_by_the_templates_own_gitignore() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "check-ignore", "--no-index", "template/.env.example.jinja"],
                            cwd=root, capture_output=True, text=True, check=False)
    assert result.returncode == 1, result.stdout  # 1: not ignored


def test_jobs_bucket_is_not_named_like_the_key_prefix(product_dir: pathlib.Path) -> None:
    """Keys start `raw/` (spec §7), so a bucket named `raw` would store raw/raw/<source>/..."""
    compose = yaml.safe_load((product_dir / "docker-compose.yml").read_text())
    assert compose["services"]["jobs"]["environment"]["RAW_BUCKET"] == "data"
    bootstrap = (product_dir / "scripts" / "bootstrap.py").read_text()
    assert 'def ensure_bucket(name: str = "data")' in bootstrap
    assert "bucket data" in bootstrap and "bucket raw" not in bootstrap
    assert 'key = f"raw/{source}/' in (product_dir / "jobs" / "jobs" / "storage.py").read_text()


def test_pytest_config_silences_copiers_dirty_tree_warning(tmp_path: pathlib.Path) -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    probe = tmp_path / "test_probe.py"
    probe.write_text("import warnings\nfrom copier.errors import DirtyLocalWarning\n\n\n"
                     "def test_warns():\n    warnings.warn(DirtyLocalWarning('dirty'))\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", str(root / "pyproject.toml"), "--rootdir", str(tmp_path),
         "-p", "no:cacheprovider", str(probe)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout
    assert "DirtyLocalWarning" not in result.stdout and "warning" not in result.stdout.lower()


SECRETS = {"ZITADEL_MASTERKEY": "m", "ZITADEL_ADMIN_PASSWORD": "z", "LAGO_RSA_PRIVATE_KEY": "r",
           "STRIPE_SECRET_KEY": "s", "LAGO_API_KEY": "k", "LAGO_ORG_USER_PASSWORD": "p"}


def _env_seen_by_host_tools(product_dir: pathlib.Path, tmp_path: pathlib.Path, target: str) -> set[str]:
    """Runs the real Makefile target with fake `uv`, `npm` and `npx` that record the secrets they see."""
    (tmp_path / "Makefile").write_text((product_dir / "Makefile").read_text())
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in SECRETS.items()))
    for folder in ["scripts", "backend", "jobs", "frontend", "e2e", "bin"]:
        (tmp_path / folder).mkdir(exist_ok=True)
    seen = tmp_path / "seen"
    seen.write_text("")
    for tool in ["uv", "npm", "npx"]:
        fake = tmp_path / "bin" / tool
        fake.write_text(f'#!/bin/sh\nenv | grep -E "^({"|".join(SECRETS)})=" | cut -d= -f1 >> "{seen}"\n')
        fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    subprocess.run(["make", "-s", target], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    return set(seen.read_text().split())


@pytest.mark.parametrize(("target", "needed"), [
    ("bootstrap", {"STRIPE_SECRET_KEY", "LAGO_API_KEY", "LAGO_ORG_USER_PASSWORD"}),
    ("brand", {"LAGO_ORG_USER_PASSWORD"}),
    ("check", set()),
    ("e2e", set()),
    ("doctor", set()),
])
def test_make_gives_host_tools_only_the_secrets_they_need(
    product_dir: pathlib.Path, tmp_path: pathlib.Path, target: str, needed: set[str]
) -> None:
    # Container-only secrets never reach the host; the rest only the targets whose scripts use them.
    assert _env_seen_by_host_tools(product_dir, tmp_path, target) == needed


@pytest.mark.parametrize(("key", "seen"), [("sk_test_x", "1"), ('"sk_test_x"', "1"), ("", ""), ('""', ""), ("''", ""),
                                           (" ", ""), ('" "', "")])
def test_e2e_is_told_whether_there_is_a_stripe_key_not_the_key(
    product_dir: pathlib.Path, tmp_path: pathlib.Path, key: str, seen: str
) -> None:
    (tmp_path / "Makefile").write_text((product_dir / "Makefile").read_text())
    (tmp_path / ".env").write_text(f"STRIPE_SECRET_KEY={key}\n")
    (tmp_path / "e2e").mkdir()
    (tmp_path / "bin").mkdir()
    out = tmp_path / "seen"
    for tool in ["npm", "npx"]:
        fake = tmp_path / "bin" / tool
        fake.write_text(f'#!/bin/sh\necho "$STRIPE_CONFIGURED/$STRIPE_SECRET_KEY" > "{out}"\n')
        fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    subprocess.run(["make", "-s", "e2e"], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    assert out.read_text().strip() == f"{seen}/"


def test_mock_payment_is_off_in_the_default_config(product_dir: pathlib.Path) -> None:
    lines = (product_dir / ".env.example").read_text().splitlines()
    assert "BILLING_MODE=" in lines and "APP_ENV=" in lines
    assert not any(line.startswith(("BILLING_MODE=mock", "APP_ENV=local")) for line in lines)
    environment = yaml.safe_load((product_dir / "docker-compose.yml").read_text())["services"]["backend"]["environment"]
    assert environment["BILLING_MODE"] == "${BILLING_MODE:-}" and environment["APP_ENV"] == "${APP_ENV:-}"
    source = (product_dir / "backend" / "app" / "config.py").read_text()
    assert 'billing_mode: str = ""' in source and 'app_env: str = ""' in source


@pytest.mark.parametrize(("mode", "seen"), [("mock", "1"), ('"mock"', "1"), ("", ""), ("fake", "")])
def test_e2e_is_told_about_mock_payment(product_dir: pathlib.Path, tmp_path: pathlib.Path, mode: str, seen: str) -> None:
    (tmp_path / "Makefile").write_text((product_dir / "Makefile").read_text())
    (tmp_path / ".env").write_text(f"BILLING_MODE={mode}\nAPP_ENV=local\n")
    (tmp_path / "e2e").mkdir()
    (tmp_path / "bin").mkdir()
    out = tmp_path / "seen"
    for tool in ["npm", "npx"]:
        fake = tmp_path / "bin" / tool
        fake.write_text(f'#!/bin/sh\necho "$MOCK_PAYMENT/$BILLING_MODE" > "{out}"\n')
        fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    run = subprocess.run(["make", "-s", "e2e"], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    assert out.read_text().strip() == f"{seen}/"
    assert ("A mock payment pass is not a Stripe pass." in run.stdout) == bool(seen)


@pytest.mark.parametrize("target", ["check", "doctor", "brand"])
def test_make_keeps_mock_payment_settings_from_other_host_tools(product_dir: pathlib.Path, tmp_path: pathlib.Path,
                                                                target: str) -> None:
    (tmp_path / "Makefile").write_text((product_dir / "Makefile").read_text())
    (tmp_path / ".env").write_text("BILLING_MODE=mock\nAPP_ENV=local\n")
    for folder in ["scripts", "backend", "jobs", "frontend", "e2e", "bin"]:
        (tmp_path / folder).mkdir(exist_ok=True)
    seen = tmp_path / "seen"
    seen.write_text("")
    for tool in ["uv", "npm", "npx"]:
        fake = tmp_path / "bin" / tool
        fake.write_text(f'#!/bin/sh\nenv | grep -E "^(BILLING_MODE|APP_ENV)=" >> "{seen}"; exit 0\n')
        fake.chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "HOME": str(tmp_path)}
    subprocess.run(["make", "-s", target], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    assert seen.read_text() == ""


def test_mock_payment_e2e_repairs_the_stack_around_a_run(product_dir: pathlib.Path) -> None:
    config = (product_dir / "e2e" / "playwright.config.ts").read_text()
    for hook in ("globalSetup", "globalTeardown"):
        assert f'{hook}: process.env.MOCK_PAYMENT ? "./mock-payment-stack.ts" : undefined' in config
    assert "export default" in (product_dir / "e2e" / "mock-payment-stack.ts").read_text()


def test_stripe_key_is_optional_in_compose(product_dir: pathlib.Path) -> None:
    compose = yaml.safe_load((product_dir / "docker-compose.yml").read_text())
    assert compose["services"]["backend"]["environment"]["STRIPE_SECRET_KEY"] == "${STRIPE_SECRET_KEY:-}"
    assert compose["services"]["stripe-cli"]["environment"]["STRIPE_API_KEY"] == "${STRIPE_SECRET_KEY:-}"


def test_published_ports_bind_only_to_loopback(product_dir: pathlib.Path) -> None:
    # The stack runs with known local credentials (postgres/postgres, Lago's superuser): never on 0.0.0.0.
    compose = yaml.safe_load((product_dir / "docker-compose.yml").read_text())
    mappings = [(name, str(port)) for name, service in compose["services"].items()
                for port in service.get("ports", [])]
    assert mappings, "no published ports found"
    assert [m for m in mappings if not m[1].startswith("127.0.0.1:")] == []


def test_zitadel_admin_gets_a_generated_password(product_dir: pathlib.Path) -> None:
    compose = yaml.safe_load((product_dir / "docker-compose.yml").read_text())
    zitadel = compose["services"]["zitadel-api"]["environment"]
    assert zitadel["ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD"] == "${ZITADEL_ADMIN_PASSWORD}"
    assert zitadel["ZITADEL_FIRSTINSTANCE_ORG_HUMAN_USERNAME"] == "admin@acme-reports.localhost"
    example = (product_dir / ".env.example").read_text()
    assert "# Generate: password 24\nZITADEL_ADMIN_PASSWORD=\n" in example


@pytest.mark.parametrize("domain", ["acme.com", "acme.localhost.com", "localhost", ".localhost"])
def test_domain_must_be_local_in_milestone_1(tmp_path: pathlib.Path, domain: str) -> None:
    with pytest.raises(ValueError, match="must end in .localhost"):
        run_copy(str(ROOT), str(tmp_path / "p"), data={**ANSWERS, "domain": domain}, defaults=True,
                 unsafe=True, vcs_ref="HEAD", quiet=True)


def test_a_subdomain_of_localhost_is_accepted(tmp_path: pathlib.Path) -> None:
    run_copy(str(ROOT), str(tmp_path / "p"), data={**ANSWERS, "domain": "dev.acme.localhost"}, defaults=True,
             unsafe=True, vcs_ref="HEAD", quiet=True)
    assert "dev.acme.localhost" in (tmp_path / "p" / "docker-compose.yml").read_text()
