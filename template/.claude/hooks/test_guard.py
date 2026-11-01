import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).with_name("guard.py")
REPO = GUARD.resolve().parents[2]


def run(tool: str, tool_input: dict[str, object], cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)})
    return subprocess.run([sys.executable, str(GUARD)], input=payload, text=True, capture_output=True,
                          check=False)


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Read", {"file_path": "/repo/.env"}),
        ("Read", {"file_path": ".env.local"}),
        ("Read", {"file_path": "/repo/.bootstrap/ids.env"}),
        ("Grep", {"pattern": "KEY", "path": ".env"}),
        ("Edit", {"file_path": ".env", "old_string": "A=", "new_string": "A=1"}),
        ("Bash", {"command": "cat .env"}),
        ("Bash", {"command": "grep KEY ./.env | head"}),
        ("Bash", {"command": "source .env && env"}),
        ("Bash", {"command": "cat .bootstrap/backend.pat"}),
        ("Bash", {"command": "ls .bootstrap"}),
        ("Bash", {"command": "git push origin main"}),
        ("Bash", {"command": "git push origin HEAD:main"}),
        ("Bash", {"command": "git push origin feat/x:refs/heads/master"}),
        ("Bash", {"command": "make check && git push --all origin"}),
        ("Bash", {"command": "git push --force origin feat/x"}),
        ("Bash", {"command": "git push -f origin feat/x"}),
        ("Bash", {"command": "git push -uf origin feat/x"}),
        ("Bash", {"command": "git push --force-with-lease origin feat/x"}),
        ("Bash", {"command": "git push origin +feat/x"}),
        ("Bash", {"command": "echo sk_live_x"}),
        ("Write", {"file_path": "x.py", "content": "KEY='sk_live_x'"}),
        ("MultiEdit", {"file_path": "x.py", "edits": [{"old_string": "a", "new_string": "sk_live_x"}]}),
    ],
)
def test_blocked(tool: str, tool_input: dict[str, object]) -> None:
    result = run(tool, tool_input)
    assert result.returncode == 2
    assert result.stderr.strip()  # the reason Claude is shown


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Read", {"file_path": "/repo/.env.example"}),
        ("Read", {"file_path": "/repo/backend/app/config.py"}),
        ("Bash", {"command": "cat .env.example"}),
        ("Bash", {"command": "git push -u origin feat/billing"}),
        ("Bash", {"command": "git push origin feat/main-page"}),
        ("Bash", {"command": "git log main..HEAD"}),
        ("Bash", {"command": "make check"}),
        ("Bash", {"command": "make env && make up && make bootstrap"}),
        ("Bash", {"command": "echo sk_test_x"}),
        # Writing files that merely mention .env or .bootstrap/ is fine; reading them is not.
        ("Edit", {"file_path": "docker-compose.yml", "old_string": "a", "new_string": "env_file: .bootstrap/ids.env"}),
        ("Write", {"file_path": "README.md", "content": "Run `make env` to write .env"}),
    ],
)
def test_allowed(tool: str, tool_input: dict[str, object]) -> None:
    result = run(tool, tool_input)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf ~/Projects",
        "rm -rf $HOME/x",
        "rm -rf ..",
        "rm -rf ../other-repo",
        "rm -rf .",
        "rm -fr /tmp/x",
        "rm -r -f /tmp/x",
        "rm --recursive --force /tmp/x",
        "sudo rm -rf /var/x",
        "cd /tmp && rm -rf x",
        "rm -rf node_modules /etc",
        "rm -rf `pwd`/x",
    ],
)
def test_rm_rf_outside_the_repo_is_blocked(command: str) -> None:
    assert run("Bash", {"command": command}).returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf frontend/node_modules",
        "rm -rf frontend/dist backend/.pytest_cache",
        "cd frontend && rm -rf node_modules",
        f"rm -rf {REPO}/frontend/dist",
        "rm -f build.log",
        "rm -r frontend/dist",
    ],
)
def test_rm_inside_the_repo_is_allowed(command: str) -> None:
    result = run("Bash", {"command": command})
    assert result.returncode == 0, result.stderr


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=cwd,
                   check=True, capture_output=True)


@pytest.mark.parametrize(("branch", "code"), [("main", 2), ("feat/x", 0)])
def test_bare_push_is_judged_by_the_current_branch(tmp_path: Path, branch: str, code: int) -> None:
    _git(tmp_path, "init", "-q", "-b", branch)
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x")
    assert run("Bash", {"command": "git push"}, cwd=tmp_path).returncode == code


def test_unreadable_input_is_blocked() -> None:
    result = subprocess.run([sys.executable, str(GUARD)], input="not json", text=True, capture_output=True,
                            check=False)
    assert result.returncode == 2
