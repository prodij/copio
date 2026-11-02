import json
import os
import pathlib
import subprocess

import pytest

DEPLOY = pathlib.Path(__file__).resolve().parents[2] / "deploy"


def stub(bin_dir: pathlib.Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\necho \"{name} $*\" >> \"$CALLS\"\n{body}\n")
    path.chmod(0o755)


@pytest.fixture
def box(tmp_path: pathlib.Path) -> dict[str, object]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    app = tmp_path / "app"
    (app / "deploy").mkdir(parents=True)
    (app / ".env").write_text("BACKEND_TAG=aaaaaaa\nJOBS_TAG=bbbbbbb\n")
    env_file = tmp_path / "app.env"
    env_file.write_text("SLUG=acme\nAWS_REGION=us-west-2\nDEPLOY_BUCKET=b\n")
    calls = tmp_path / "calls"
    calls.write_text("")
    stub(bin_dir, "docker", 'case "$*" in *"ps --status"*) echo jobs;; esac; exit 0')
    stub(bin_dir, "curl", "exit 0")
    stub(bin_dir, "sleep", "exit 0")
    stub(bin_dir, "aws", "exit 0")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "CALLS": str(calls),
           "APP_DIR": str(app), "APP_ENV_FILE": str(env_file)}
    return {"bin": bin_dir, "app": app, "calls": calls, "env": env}


def deploy(box: dict[str, object], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(DEPLOY / "deploy.sh"), *args], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                          capture_output=True, text=True, check=False)


def env_text(box: dict[str, object]) -> str:
    return (box["app"] / ".env").read_text()  # type: ignore[operator]


def calls(box: dict[str, object]) -> str:
    return box["calls"].read_text()  # type: ignore[union-attr]


def test_backend_deploy_migrates_before_starting_and_records_the_tag(box: dict[str, object]) -> None:
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 0, result.stderr
    assert "BACKEND_TAG=abc1234" in env_text(box)
    log = calls(box)
    assert log.index("alembic") < log.index("up -d backend")
    assert "ssm put-parameter --name /acme/tags/backend --value abc1234" in log


def test_failed_migration_keeps_the_old_version(box: dict[str, object]) -> None:
    stub(box["bin"], "docker", 'case "$*" in *alembic*) exit 1;; esac; exit 0')  # type: ignore[arg-type]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "BACKEND_TAG=aaaaaaa" in env_text(box)
    assert "up -d backend" not in calls(box)


def test_failed_health_check_rolls_back(box: dict[str, object]) -> None:
    stub(box["bin"], "curl", "exit 7")  # type: ignore[arg-type]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "BACKEND_TAG=aaaaaaa" in env_text(box)
    assert calls(box).count("up -d backend") == 2
    assert "put-parameter" not in calls(box)


@pytest.mark.parametrize(("service", "tag"), [("postgres", "abc1234"), ("backend", "latest"),
                                              ("backend", "abc; rm -rf /"), ("", ""), ("jobs", "")])
def test_bad_input_is_refused(box: dict[str, object], service: str, tag: str) -> None:
    result = deploy(box, service, tag)
    assert result.returncode == 2
    assert "docker" not in calls(box)


def test_jobs_deploy_needs_no_migration(box: dict[str, object]) -> None:
    assert deploy(box, "jobs", "abc1234").returncode == 0
    assert "alembic" not in calls(box)
    assert "JOBS_TAG=abc1234" in env_text(box)


def run_start(box: dict[str, object], bootstrap_secret: str) -> subprocess.CompletedProcess[str]:
    stub(box["bin"], "aws", f"""
case "$*" in
  *"--secret-id acme/app"*) echo '{json.dumps({"LAGO_API_KEY": "k"})}';;
  *"--secret-id acme/bootstrap"*) echo '{bootstrap_secret}';;
  *"/acme/config"*) echo '{json.dumps({"DOMAIN": "x.test", "ECR_REGISTRY": "r"})}';;
  *"/acme/tags/backend"*) echo aaaaaaa;;
  *"/acme/tags/jobs"*) echo bbbbbbb;;
  *) exit 0;;
esac""")  # type: ignore[arg-type]
    return subprocess.run(["bash", str(DEPLOY / "start.sh")], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                          capture_output=True, text=True, check=False)


def test_replaced_server_restores_tokens_and_starts(box: dict[str, object]) -> None:
    secret = json.dumps({"admin_pat": "A", "login_client_pat": "L", "backend_pat": "B", "ids_env": "X=1\n"})
    result = run_start(box, secret)
    assert result.returncode == 0, result.stderr
    app = box["app"]
    assert (app / ".bootstrap/zitadel/admin.pat").read_text().strip() == "A"  # type: ignore[operator]
    assert (app / ".bootstrap/backend/backend.pat").read_text().strip() == "B"  # type: ignore[operator]
    assert "up -d" in calls(box)
    assert "zitadel-init" not in calls(box)
    env = (app / ".env").read_text()  # type: ignore[operator]
    assert "LAGO_API_KEY=k" in env and "DOMAIN=x.test" in env and "BACKEND_TAG=aaaaaaa" in env
    assert oct((app / ".env").stat().st_mode)[-3:] == "600"  # type: ignore[operator]


def test_new_server_before_first_run_does_not_start_the_stack(box: dict[str, object]) -> None:
    result = run_start(box, "{}")
    assert result.returncode == 0, result.stderr
    assert "up -d" not in calls(box)


def test_first_run_hands_bootstrap_its_settings_without_printing_them(box: dict[str, object]) -> None:
    app = box["app"]
    (app / "scripts").mkdir()  # type: ignore[operator]
    (app / "deploy" / "db-init.sql").write_text("select 1;\n")  # type: ignore[operator]
    seen = app.parent / "uv-env"  # type: ignore[attr-defined]
    stub(box["bin"], "uv", f'env > "{seen}"')  # type: ignore[arg-type]
    app_secret = {"LAGO_API_KEY": "key-s3cret", "LAGO_ORG_USER_PASSWORD": "pw-s3cret",
                  "DB_ADMIN_SECRET_ARN": "arn:admin", "APP_DB_PASSWORD": "a", "LAGO_DB_PASSWORD": "l"}
    stub(box["bin"], "aws", f"""
case "$*" in
  *"--secret-id acme/app"*) echo '{json.dumps(app_secret)}';;
  *"--secret-id acme/bootstrap"*) echo '{{}}';;
  *"--secret-id arn:admin"*) echo '{json.dumps({"password": "admin-s3cret"})}';;
  *"/acme/config"*) echo '{json.dumps({"DOMAIN": "x.test", "ECR_REGISTRY": "r", "DB_HOST": "h"})}';;
  *) echo aaaaaaa;;
esac""")  # type: ignore[arg-type]
    for name in ("start.sh", "first-run.sh"):
        (app / "deploy" / name).write_bytes((DEPLOY / name).read_bytes())  # type: ignore[operator]
        (app / "deploy" / name).chmod(0o755)  # type: ignore[operator]
    result = subprocess.run(["bash", str(DEPLOY / "first-run.sh")], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    got = dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)
    assert got["DEPLOY_TARGET"] == "aws"
    assert got["SLUG"] == "acme"
    assert got["DOMAIN"] == "x.test"
    assert got["LAGO_API_KEY"] == "key-s3cret"
    assert got["LAGO_ORG_USER_PASSWORD"] == "pw-s3cret"
    assert got["LAGO_ORG_USER_EMAIL"] == "admin@x.test"
    assert "DB_ADMIN_PASSWORD" not in got
    assert got["STRIPE_SECRET_KEY"] == ""  # absent from .env, and first-run still goes on
    for secret in ("key-s3cret", "pw-s3cret", "admin-s3cret"):
        assert secret not in result.stdout + result.stderr
    assert "uv run python -u bootstrap.py" in calls(box)


def counting_docker(box: dict[str, object], body: str) -> None:
    """A docker stub with a per-pattern counter: `n` is how many times the stub has run before."""
    stub(box["bin"], "docker", f'n=$(cat "$CALLS.n" 2>/dev/null || echo 0); echo $((n+1)) > "$CALLS.n"\n{body}')  # type: ignore[arg-type]


def test_failed_pull_keeps_the_old_version(box: dict[str, object]) -> None:
    stub(box["bin"], "docker", 'case "$*" in *pull*) exit 1;; esac; exit 0')  # type: ignore[arg-type]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "BACKEND_TAG=aaaaaaa" in env_text(box)
    assert "up -d" not in calls(box)


def test_failed_start_rolls_back_and_says_when_the_restart_fails_too(box: dict[str, object]) -> None:
    stub(box["bin"], "docker", 'case "$*" in *"up -d"*) exit 1;; esac; exit 0')  # type: ignore[arg-type]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "BACKEND_TAG=aaaaaaa" in env_text(box)
    assert calls(box).count("up -d backend") == 2
    assert "the service may be down" in result.stderr
    assert "put-parameter" not in calls(box)


def test_failed_start_with_a_good_restart_is_quiet_about_downtime(box: dict[str, object]) -> None:
    counting_docker(box, 'case "$*" in *"up -d"*) [ "$(grep -c "up -d" "$CALLS")" -le 1 ] && exit 1;; esac; exit 0')
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "may be down" not in result.stderr
    assert "BACKEND_TAG=aaaaaaa" in env_text(box)


def test_unrecorded_tag_retries_then_fails_but_keeps_the_new_version(box: dict[str, object]) -> None:
    stub(box["bin"], "aws", 'case "$*" in *put-parameter*) exit 1;; esac; exit 0')  # type: ignore[arg-type]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "deployed but not recorded" in result.stderr
    assert calls(box).count("put-parameter") == 3
    assert calls(box).count("up -d backend") == 1
    assert "BACKEND_TAG=abc1234" in env_text(box)


def test_missing_previous_tag_refuses_before_touching_anything(box: dict[str, object]) -> None:
    (box["app"] / ".env").write_text("JOBS_TAG=bbbbbbb\n")  # type: ignore[operator]
    result = deploy(box, "backend", "abc1234")
    assert result.returncode == 1
    assert "docker" not in calls(box)
    assert env_text(box) == "JOBS_TAG=bbbbbbb\n"


def test_jobs_that_run_once_and_then_stop_are_rolled_back(box: dict[str, object]) -> None:
    counting_docker(box, 'case "$*" in *"ps --status"*) [ "$(grep -c "ps --status" "$CALLS")" -eq 1 ] && echo jobs;; esac; exit 0')
    result = deploy(box, "jobs", "abc1234")
    assert result.returncode == 1
    assert "JOBS_TAG=bbbbbbb" in env_text(box)
    assert "put-parameter" not in calls(box)


def test_jobs_that_flap_never_reach_five_in_a_row(box: dict[str, object]) -> None:
    counting_docker(box, 'case "$*" in *"ps --status"*) [ $(( $(grep -c "ps --status" "$CALLS") % 2 )) -eq 1 ] && echo jobs;; esac; exit 0')
    assert deploy(box, "jobs", "abc1234").returncode == 1
    assert "JOBS_TAG=bbbbbbb" in env_text(box)


def test_jobs_need_five_running_polls_before_the_tag_is_recorded(box: dict[str, object]) -> None:
    assert deploy(box, "jobs", "abc1234").returncode == 0
    assert calls(box).count("ps --status") == 5


def test_deploys_take_the_lock_when_flock_exists(box: dict[str, object]) -> None:
    stub(box["bin"], "flock", "exit 0")  # type: ignore[arg-type]
    assert deploy(box, "backend", "abc1234").returncode == 0
    assert "flock -w 600 9" in calls(box)


def test_unreadable_env_file_fails(box: dict[str, object]) -> None:
    box["env"]["APP_ENV_FILE"] = "/nonexistent/app.env"  # type: ignore[index]
    assert deploy(box, "backend", "abc1234").returncode == 1


def test_bootstrap_secret_access_denied_stops_start(box: dict[str, object]) -> None:
    stub(box["bin"], "aws", """
case "$*" in
  *"--secret-id acme/app"*) echo '{"LAGO_API_KEY": "k"}';;
  *"--secret-id acme/bootstrap"*) echo "An error occurred (AccessDeniedException) when calling" >&2; exit 254;;
  *"/acme/config"*) echo '{"DOMAIN": "x.test", "ECR_REGISTRY": "r"}';;
  *) echo aaaaaaa;;
esac""")  # type: ignore[arg-type]
    result = subprocess.run(["bash", str(DEPLOY / "start.sh")], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                            capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "AccessDeniedException" in result.stderr
    assert "up -d" not in calls(box)


def test_empty_bootstrap_secret_means_no_tokens_yet(box: dict[str, object]) -> None:
    stub(box["bin"], "aws", """
case "$*" in
  *"--secret-id acme/app"*) echo '{"LAGO_API_KEY": "k"}';;
  *"--secret-id acme/bootstrap"*) echo "An error occurred (ResourceNotFoundException)" >&2; exit 254;;
  *"/acme/config"*) echo '{"DOMAIN": "x.test", "ECR_REGISTRY": "r"}';;
  *) echo aaaaaaa;;
esac""")  # type: ignore[arg-type]
    result = subprocess.run(["bash", str(DEPLOY / "start.sh")], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "up -d" not in calls(box)


def test_bootstrap_secret_that_is_not_json_stops_start_without_printing_it(box: dict[str, object]) -> None:
    result = run_start(box, "not-json-s3cret")
    assert result.returncode != 0
    assert "s3cret" not in result.stdout + result.stderr


def test_partial_bootstrap_secret_stops_start(box: dict[str, object]) -> None:
    result = run_start(box, json.dumps({"admin_pat": "A"}))
    assert result.returncode != 0
    assert "up -d" not in calls(box)


def test_tag_read_failure_leaves_the_good_env_alone(box: dict[str, object]) -> None:
    before = env_text(box)
    stub(box["bin"], "aws", """
case "$*" in
  *"--secret-id acme/app"*) echo '{"LAGO_API_KEY": "k"}';;
  *"/acme/config"*) echo '{"DOMAIN": "x.test", "ECR_REGISTRY": "r"}';;
  *"/acme/tags/backend"*) echo "ThrottlingException" >&2; exit 254;;
  *) echo bbbbbbb;;
esac""")  # type: ignore[arg-type]
    result = subprocess.run(["bash", str(DEPLOY / "start.sh")], env=box["env"],  # type: ignore[arg-type]  # noqa: S607
                            capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert env_text(box) == before
