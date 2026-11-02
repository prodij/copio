import json
import pathlib
import re
import subprocess
from typing import Any

import pytest
import yaml

from conftest import ROOT

WORKFLOWS = sorted([*ROOT.glob(".github/workflows/*.yml"), *ROOT.glob("template/.github/workflows/*.yml")])
PINNED = re.compile(r"^\s*(-\s+)?uses:\s+[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+\s*$")


def test_every_action_is_pinned_to_a_commit() -> None:
    assert len(WORKFLOWS) >= 6
    for path in WORKFLOWS:
        yaml.safe_load(path.read_text())
        for line in path.read_text().splitlines():
            if re.match(r"^\s*(-\s+)?uses:", line):
                assert PINNED.match(line), f"{path.relative_to(ROOT)}: {line.strip()}"


E2E_WORKFLOWS = [ROOT / ".github/workflows/template.yml", ROOT / "template/.github/workflows/e2e.yml"]


def _stripe_step(path: pathlib.Path) -> dict[str, Any]:
    jobs = yaml.safe_load(path.read_text())["jobs"]
    steps = [step for job in jobs.values() for step in job["steps"]]
    return next(step for step in steps if 'case "$STRIPE_SECRET_KEY"' in step.get("run", ""))


def _run_stripe_guard(path: pathlib.Path, tmp_path: pathlib.Path, key: str, required: str) -> tuple[int, str, str]:
    """Runs the step's checks, everything before it writes .env; returns (exit code, output, step summary)."""
    guard = _stripe_step(path)["run"].split("umask")[0]
    summary = tmp_path / "summary"
    summary.write_text("")
    env = {"STRIPE_SECRET_KEY": key, "STRIPE_E2E_REQUIRED": required, "GITHUB_STEP_SUMMARY": str(summary)}
    result = subprocess.run(["/bin/sh", "-e", "-c", guard], env=env, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, summary.read_text()


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
@pytest.mark.parametrize("required", ["", "true"])
@pytest.mark.parametrize("key", ["sk_live_x", "rk_test_x", "x", " "])
def test_ci_refuses_every_stripe_key_but_a_test_key(path: pathlib.Path, tmp_path: pathlib.Path, key: str,
                                                    required: str) -> None:
    code, out, _ = _run_stripe_guard(path, tmp_path, key, required)
    assert code == 1 and "must be a Stripe TEST key" in out


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
@pytest.mark.parametrize("required", ["", "true"])
def test_ci_runs_with_a_test_key_and_no_note(path: pathlib.Path, tmp_path: pathlib.Path, required: str) -> None:
    assert _run_stripe_guard(path, tmp_path, "sk_test_x", required) == (0, "", "")


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
@pytest.mark.parametrize("required", ["", "false"])
def test_ci_without_a_key_says_the_payment_test_is_skipped(path: pathlib.Path, tmp_path: pathlib.Path,
                                                           required: str) -> None:
    code, out, summary = _run_stripe_guard(path, tmp_path, "", required)
    assert code == 0 and "::notice::" in out and "skipped" in summary


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
def test_ci_without_a_key_fails_when_stripe_e2e_is_required(path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    code, out, summary = _run_stripe_guard(path, tmp_path, "", "true")
    assert code == 1 and "::error::" in out and summary == ""


def _env_written_by_ci(path: pathlib.Path, tmp_path: pathlib.Path, key: str) -> str:
    """Runs the part of the step that writes .env, in a temp dir with a do-nothing `make`."""
    written = "umask" + _stripe_step(path)["run"].split("umask", 1)[1]
    (tmp_path / "make").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / "make").chmod(0o755)
    env = {"STRIPE_SECRET_KEY": key, "PATH": f"{tmp_path}:/usr/bin:/bin"}
    subprocess.run(["/bin/sh", "-e", "-c", written], cwd=tmp_path, env=env, check=True)
    return (tmp_path / ".env").read_text()


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
def test_ci_turns_on_mock_payment_only_with_no_key_and_says_it_is_not_stripe(path: pathlib.Path,
                                                                             tmp_path: pathlib.Path) -> None:
    assert _env_written_by_ci(path, tmp_path, "") == "STRIPE_SECRET_KEY=\nBILLING_MODE=mock\nAPP_ENV=local\n"
    assert _env_written_by_ci(path, tmp_path, "sk_test_x") == "STRIPE_SECRET_KEY=sk_test_x\n"
    _, out, summary = _run_stripe_guard(path, tmp_path, "", "")
    assert "mock payment" in out and "not a Stripe pass" in summary


@pytest.mark.parametrize("path", E2E_WORKFLOWS)
def test_ci_reads_the_switch_from_a_repo_variable(path: pathlib.Path) -> None:
    assert _stripe_step(path)["env"] == {"STRIPE_SECRET_KEY": "${{ secrets.STRIPE_SECRET_KEY }}",
                                         "STRIPE_E2E_REQUIRED": "${{ vars.STRIPE_E2E_REQUIRED }}"}


def test_product_gets_agent_rules_and_the_guard(product_dir: pathlib.Path) -> None:
    claude = (product_dir / "CLAUDE.md").read_text()
    assert claude.startswith("# Acme Reports") and "{{" not in claude
    settings = json.loads((product_dir / ".claude" / "settings.json").read_text())
    hook = settings["hooks"]["PreToolUse"][0]
    assert "Bash" in hook["matcher"] and "Read" in hook["matcher"]
    assert hook["hooks"][0]["command"].endswith('.claude/hooks/guard.py"')
    assert (product_dir / ".claude" / "hooks" / "test_guard.py").exists()
    assert "acme-reports.localhost" in (product_dir / "e2e" / "playwright.config.ts").read_text()
