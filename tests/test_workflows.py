import json
import pathlib
import re

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


def test_product_gets_agent_rules_and_the_guard(product_dir: pathlib.Path) -> None:
    claude = (product_dir / "CLAUDE.md").read_text()
    assert claude.startswith("# Acme Reports") and "{{" not in claude
    settings = json.loads((product_dir / ".claude" / "settings.json").read_text())
    hook = settings["hooks"]["PreToolUse"][0]
    assert "Bash" in hook["matcher"] and "Read" in hook["matcher"]
    assert hook["hooks"][0]["command"].endswith('.claude/hooks/guard.py"')
    assert (product_dir / ".claude" / "hooks" / "test_guard.py").exists()
    assert "acme-reports.localhost" in (product_dir / "e2e" / "playwright.config.ts").read_text()
