import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).with_name("guard.py")
REPO = GUARD.resolve().parents[2]
LIVE = "sk_live_" + "a1B2" * 6  # built at run time: no key-shaped string in the repo


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
        ("Bash", {"command": f"echo {LIVE}"}),
        ("Write", {"file_path": "x.py", "content": f"KEY='{LIVE}'"}),
        ("MultiEdit", {"file_path": "x.py", "edits": [{"old_string": "a", "new_string": LIVE}]}),
        ("Bash", {"command": "echo rk_live_" + "x" * 24}),
        # globs and quoting that reach .env or .bootstrap/
        ("Bash", {"command": "cat .en*"}),
        ("Bash", {"command": "cat ./.e?v"}),
        ("Bash", {"command": "cat .[e]nv"}),
        ("Bash", {"command": "cat .env.l*"}),
        ("Bash", {"command": "ls .bootstr*/"}),
        ("Bash", {"command": 'cat .e""nv'}),
        ("Bash", {"command": "cat '.env'"}),
        ("Bash", {"command": "cat {.env,README.md}"}),
        ("Bash", {"command": "head -n1 <.env"}),
        ("Bash", {"command": "find . -name '.env*' -exec cat {} +"}),
        # recursive grep over the repo (or above it) reads git-ignored files too
        ("Bash", {"command": "grep -r KEY ."}),
        ("Bash", {"command": "grep -rn KEY"}),
        ("Bash", {"command": "grep --recursive -e KEY"}),
        ("Bash", {"command": f"grep -R KEY {REPO.parent}"}),
        ("Bash", {"command": "grep -rn KEY . --exclude=.env*"}),  # .bootstrap/ still searched
        ("Grep", {"pattern": "KEY", "glob": "*"}),
        ("Grep", {"pattern": "KEY", "glob": ".env*"}),
        ("Grep", {"pattern": "KEY", "glob": "**/.bootstrap/**"}),
        ("Bash", {"command": "docker compose config"}),
        ("Bash", {"command": "docker compose -f docker-compose.yml config --format json"}),
        ("Bash", {"command": "docker-compose config"}),
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
        # placeholders in tests stay editable; only realistic live keys are blocked
        ("Bash", {"command": "echo sk_live_x"}),
        ("Write", {"file_path": "x.py", "content": "KEY='sk_live_x'"}),
        ("Bash", {"command": "grep -rn KEY backend/ frontend/src"}),
        ("Bash", {"command": "grep -rn KEY . --exclude=.env* --exclude-dir=.bootstrap"}),
        ("Bash", {"command": "git grep -n KEY"}),
        ("Bash", {"command": "rg KEY"}),
        ("Bash", {"command": "grep KEY backend/app/config.py"}),
        ("Grep", {"pattern": "KEY", "glob": "*.py"}),
        ("Grep", {"pattern": "KEY", "glob": "*.{ts,tsx}"}),
        ("Bash", {"command": "docker compose ps"}),
        ("Bash", {"command": "find . -name '*.pyc' -delete"}),
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
        "rm -rf $(pwd)",
        # wrappers
        "/bin/rm -rf /tmp/x",
        "(rm -rf /tmp/x)",
        "(cd /tmp; rm -rf x)",
        "env FOO=1 rm -rf /tmp/x",
        "env -u HOME rm -rf /tmp/x",
        "timeout 5 rm -rf /tmp/x",
        'bash -c "rm -rf /tmp/x"',
        "sh -c 'cd / && rm -rf tmp'",
        "find . -name x | xargs rm -rf",
        "xargs -0 /bin/rm -r < list",
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
        "rm -rf frontend/dist 2>/dev/null",
        "bash -c 'rm -rf frontend/dist'",
        "find . -name '*.pyc' | xargs rm -f",
    ],
)
def test_rm_inside_the_repo_is_allowed(command: str) -> None:
    result = run("Bash", {"command": command})
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git -c core.pager=cat --no-pager push origin main",
        "git --git-dir=.git push origin main",
        "git -C . push --force origin feat/x",
        "env -i git push origin HEAD:main",
        "sudo -u me git push --force origin x",
        "sh -c 'git push origin main'",
        "(git push origin main)",
        "/usr/bin/git push origin main",
    ],
)
def test_wrapped_pushes_are_blocked(command: str) -> None:
    assert run("Bash", {"command": command}).returncode == 2


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


@pytest.mark.parametrize(
    "command",
    [
        "terraform apply tfplan",
        "cd infra && terraform destroy",
        "terraform -chdir=infra apply",
        "tofu apply",
        "terraform state rm aws_db_instance.main",
        "terraform force-unlock abc",
        "make infra-apply",
        "make infra-destroy",
        "make infra-secrets",
        "make infra-set-stripe-key",
        "make infra-release",
        "make infra-bootstrap",
        "aws secretsmanager get-secret-value --secret-id x",
        "aws --profile p secretsmanager get-secret-value --secret-id x",
        "aws --region r secretsmanager get-secret-value --secret-id x",
        "aws secretsmanager batch-get-secret-value --secret-id-list x",
        "terraform test",
        "terraform refresh",
        "terraform workspace new x",
        "gmake infra-apply",
    ],
)
def test_infrastructure_writes_are_blocked(command: str) -> None:
    assert run("Bash", {"command": command}).returncode == 2


@pytest.mark.parametrize(
    "command",
    ["terraform plan -out=tfplan", "terraform -chdir=infra validate", "terraform fmt -check",
     "make infra-plan", "make infra-doctor", "cat infra/README.md"],
)
def test_infrastructure_reads_are_allowed(command: str) -> None:
    assert run("Bash", {"command": command}).returncode == 0
