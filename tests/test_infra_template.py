import json
import pathlib
import re
import shutil
import subprocess

import pytest
import yaml

from conftest import ROOT

# Attribute values that aren't AWS resource names.
NOT_RESOURCE_NAMES = {
    "image-id",
    "Product",
    "TagKeyValue",
    "Managed-CachingOptimized",
    "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
    "deploy",  # the SSM document's step name
}


def tf_files(product_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted((product_dir / "infra").glob("*.tf"))


def test_tfvars_has_the_slug_and_no_secrets(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "terraform.tfvars").read_text()
    assert re.search(r'^slug\s*=\s*"acme-reports"', text, re.M)
    assert not re.search(r"(password|secret|token)\s*=", text, re.I)


def test_every_named_resource_uses_the_slug(product_dir: pathlib.Path) -> None:
    pattern = re.compile(r'^\s*(name|identifier|bucket|name_prefix)\s*=\s*"([^"]+)"', re.M)
    for path in tf_files(product_dir):
        for _, value in pattern.findall(path.read_text()):
            if value not in NOT_RESOURCE_NAMES:
                assert "local.name" in value or "var.domain" in value, f"{path.name}: {value}"


def test_provider_refuses_other_accounts(product_dir: pathlib.Path) -> None:
    assert "allowed_account_ids" in (product_dir / "infra" / "versions.tf").read_text()


def test_no_nat_gateway_and_no_ssh(product_dir: pathlib.Path) -> None:
    text = "\n".join(p.read_text() for p in tf_files(product_dir))
    assert "aws_nat_gateway" not in text
    assert "from_port   = 22" not in text


@pytest.mark.slow
def test_terraform_is_valid(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    assert shutil.which("terraform"), "terraform is required for this test"
    infra = tmp_path / "infra"
    shutil.copytree(product_dir / "infra", infra)
    subprocess.run(["terraform", "fmt", "-check", "-recursive"], cwd=infra, check=True)
    subprocess.run(["terraform", "init", "-backend=false", "-input=false"], cwd=infra, check=True)
    subprocess.run(["terraform", "validate"], cwd=infra, check=True)


def test_database_is_private_protected_and_backed_up(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "database.tf").read_text()
    assert "publicly_accessible         = false" in text
    assert "manage_master_user_password = true" in text
    assert "deletion_protection         = var.protect" in text
    assert "backup_retention_period     = 7" in text
    assert 'engine_version              = "15"' in text


def test_terraform_never_holds_secret_values(product_dir: pathlib.Path) -> None:
    text = "\n".join(p.read_text() for p in tf_files(product_dir))
    assert "aws_secretsmanager_secret_version" not in text
    assert "aws_iam_access_key" not in text
    assert "random_password" not in text


def test_ses_user_can_be_destroyed_with_its_out_of_band_key(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "email.tf").read_text()
    assert "force_destroy = true" in text
    assert "aws_route53_record.ses_verification" in text


def test_server_has_no_ssh_uses_imds_v2_and_reaches_the_role_from_containers(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "server.tf").read_text()
    assert "key_name" not in text
    assert 'http_tokens                 = "required"' in text
    assert "http_put_response_hop_limit = 2" in text
    assert "encrypted   = true" in text
    assert "ignore_changes = [ami, user_data]" in text


def test_server_opens_only_web_ports(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "server.tf").read_text()
    assert re.findall(r"from_port\s*=\s*(\d+)", text.split('resource "aws_iam_role"')[0]) == ["80", "443", "0"]


def test_deploy_role_is_limited_to_main_and_has_no_terraform_or_secrets(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "ci.tf").read_text()
    assert "repo:${var.github_repo}:ref:refs/heads/main" in text
    assert "secretsmanager" not in text
    assert "AdministratorAccess" not in text
    assert 'allowedValues = ["backend", "jobs"]' in text


def test_second_product_can_skip_the_oidc_provider(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "ci.tf").read_text()
    assert re.search(r"count\s*=\s*var\.create_github_oidc_provider \? 1 : 0", text)
    assert 'data "aws_iam_openid_connect_provider" "github"' in text


def aws_compose(product_dir: pathlib.Path) -> dict:
    return yaml.safe_load((product_dir / "docker-compose.aws.yml").read_text())


def test_aws_compose_has_no_local_stand_ins_or_payment_shortcuts(product_dir: pathlib.Path) -> None:
    text = (product_dir / "docker-compose.aws.yml").read_text().lower()
    services = aws_compose(product_dir)["services"]
    for name in ["stripe-cli", "postgres", "s3", "frontend"]:
        assert name not in services, name
    assert "mock" not in text


def test_only_caddy_is_public(product_dir: pathlib.Path) -> None:
    for name, service in aws_compose(product_dir)["services"].items():
        for port in service.get("ports", []):
            if name != "caddy":
                assert str(port).startswith("127.0.0.1:"), f"{name}: {port}"


def test_database_connections_require_tls(product_dir: pathlib.Path) -> None:
    text = (product_dir / "docker-compose.aws.yml").read_text()
    assert text.count("sslmode=require") >= 3
    assert "SSL_MODE: require" in text
    assert "SSL_MODE: disable" not in text


def test_only_the_setup_service_gets_the_database_admin_password(product_dir: pathlib.Path) -> None:
    services = aws_compose(product_dir)["services"]
    for name, service in services.items():
        if "DB_ADMIN_PASSWORD" in str(service.get("environment", "")):
            assert name == "zitadel-init"
    assert services["zitadel-init"]["profiles"] == ["setup"]


def test_caddy_keeps_lago_private_except_webhooks(product_dir: pathlib.Path) -> None:
    text = (product_dir / "deploy" / "Caddyfile").read_text()
    assert "@webhooks path /webhooks/*" in text
    assert text.count("respond 403") == 3
    # Under /debug/, only what make infra-doctor and bootstrap call is public.
    assert "handle /debug/ready {" in text
    assert "@debug path /debug /debug/*" in text


def test_aws_compose_config_is_valid(product_dir: pathlib.Path) -> None:
    assert shutil.which("docker"), "docker is required for this test"
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.aws.yml", "--profile", "setup", "config", "--quiet", "--no-interpolate"],
        cwd=product_dir, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_make_has_every_infra_command(product_dir: pathlib.Path) -> None:
    makefile = (product_dir / "Makefile").read_text()
    for target in ["infra-init", "infra-plan", "infra-apply", "infra-secrets", "infra-set-stripe-key",
                   "infra-release", "infra-bootstrap", "infra-doctor", "infra-destroy"]:
        assert f"\n{target}:" in makefile, target


def rehearsal_compose(product_dir: pathlib.Path) -> dict:
    """The AWS file with the rehearsal's override applied, as Compose itself merges them."""
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.aws.yml", "-f", "deploy/rehearsal/docker-compose.rehearsal.yml",
         "--profile", "setup", "config", "--no-interpolate", "--format", "json"],
        cwd=product_dir, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_rehearsal_files_exist_and_are_not_ignored(product_dir: pathlib.Path) -> None:
    for rel in ["rehearsal.env", "docker-compose.rehearsal.yml", "run.sh"]:
        assert (product_dir / "deploy" / "rehearsal" / rel).is_file(), rel
    assert ".rehearsal/" in (product_dir / ".gitignore").read_text().splitlines()
    makefile = (product_dir / "Makefile").read_text()
    assert "\nrehearse-aws:" in makefile
    assert re.search(r"^\.PHONY:.*\brehearse-aws\b", makefile, re.M)


def test_rehearsal_publishes_no_ports(product_dir: pathlib.Path) -> None:
    assert shutil.which("docker"), "docker is required for this test"
    services = rehearsal_compose(product_dir)["services"]
    assert "db" in services and "caddy" in services and "lago-api" in services
    for name, service in services.items():
        if name == "backend":  # never started: it has no image here, and run.sh names what it starts
            continue
        assert not service.get("ports"), f"{name}: {service.get('ports')}"


def test_rehearsals_zitadel_services_dont_mount_the_products_bootstrap_folder(product_dir: pathlib.Path) -> None:
    # `backend` still mounts it, and is never started here.
    services = rehearsal_compose(product_dir)["services"]
    for name in ["zitadel-api", "zitadel-login"]:
        sources = [volume["source"] for volume in services[name]["volumes"]]
        assert not any(".bootstrap" in source for source in sources), f"{name}: {sources}"


def test_rehearsal_env_has_no_key_and_covers_what_compose_needs(product_dir: pathlib.Path) -> None:
    text = (product_dir / "deploy" / "rehearsal" / "rehearsal.env").read_text()
    assert "PRIVATE KEY" not in text and "LAGO_RSA_PRIVATE_KEY" not in text  # run.sh generates it
    # Zitadel's setup refuses a first-instance SMTP host without a port, and AWS always gives it one.
    assert re.search(r"^SMTP_HOST=\S+:\d+$", text, re.M)


def test_lago_migrations_run_instead_of_loading_structure_sql(product_dir: pathlib.Path) -> None:
    # Loading it drops and recreates pg_partman, which Lago's non-superuser role can't do.
    command = aws_compose(product_dir)["services"]["lago-migrate"]["command"]
    assert "rm -f db/structure.sql" in " ".join(command)


def test_rehearsal_asks_what_the_doctor_asks(product_dir: pathlib.Path) -> None:
    query = "select count(*) from partman.part_config where parent_table='public.enriched_events'"
    assert query in (product_dir / "deploy" / "rehearsal" / "run.sh").read_text()
    assert query in (product_dir / "scripts" / "infra_doctor.py").read_text()


def test_runbook_covers_every_step_in_order(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "README.md").read_text()
    order = ["make infra-init", "make infra-plan", "make infra-apply", "make infra-secrets",
             "make infra-release", "make infra-bootstrap", "make infra-doctor"]
    positions = [text.index(step) for step in order]
    assert positions == sorted(positions)
    for needed in ["destroy", "replace", "SES", "sandbox", "Product", "make infra-destroy", "restore",
                   "make rehearse-aws", "part_config", "run_maintenance", "structure.sql"]:
        assert needed in text, needed


def test_runbook_commands_exist(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "README.md").read_text()
    makefile = (product_dir / "Makefile").read_text()
    for target in set(re.findall(r"make ((?:infra|rehearse)-[a-z-]+)", text)):
        assert re.search(rf"^{re.escape(target)}:", makefile, re.M), target
    for workflow in set(re.findall(r"gh workflow run ([a-z-]+)", text)):
        assert (product_dir / ".github" / "workflows" / f"{workflow}.yml").exists(), workflow
    for output in set(re.findall(r"terraform output -raw ([a-z_]+)", text)):
        assert any(f'output "{output}"' in f.read_text() for f in tf_files(product_dir)), output
    for needed in ["--document-name ", "-deploy", "service=backend,tag=", "get-command-invocation", "roll forward"]:
        assert needed in text, needed
    document = re.search(r'resource "aws_ssm_document" "deploy" \{\s*name\s*=\s*"\$\{local\.name\}-deploy"', "".join(f.read_text() for f in tf_files(product_dir)))
    assert document, "the runbook's <slug>-deploy document is not in infra/"
    ci = (product_dir / "infra" / "ci.tf").read_text()
    for param in ["service", "tag"]:
        assert re.search(rf"^\s*{param}\s*=\s*\{{ type", ci, re.M), param


def resource_block(text: str, kind: str, name: str) -> str:
    return re.search(rf'resource "{kind}" "{name}" \{{.*?^\}}', text, re.S | re.M)[0]


def test_alarms_cover_a_lost_server_without_recovering_a_healthy_one(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "monitoring.tf").read_text()
    assert 'treat_missing_data  = "breaching"' in resource_block(text, "aws_cloudwatch_metric_alarm", "server_unhealthy")
    assert 'treat_missing_data  = "missing"' in resource_block(text, "aws_cloudwatch_metric_alarm", "server_recover")


def test_database_events_reach_the_topic(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "monitoring.tf").read_text()
    subscription = resource_block(text, "aws_db_event_subscription", "database")
    assert "sns_topic        = aws_sns_topic.alerts.arn" in subscription
    assert "aws_db_instance.main.identifier" in subscription
    for category in ["availability", "failover", "failure", "low storage"]:
        assert f'"{category}"' in subscription
    policy = resource_block(text, "aws_sns_topic_policy", "alerts")
    for principal in ["events.rds.amazonaws.com", "cloudwatch.amazonaws.com", "AWS:SourceOwner"]:
        assert principal in policy
    assert text.count("aws_sns_topic_policy") == 2  # the policy, and the subscription waiting for it


def test_budget_emails_directly(product_dir: pathlib.Path) -> None:
    # So the topic's policy has no statement for budgets. Point the budget at the topic and it needs one.
    text = (product_dir / "infra" / "monitoring.tf").read_text()
    budget = resource_block(text, "aws_budgets_budget", "monthly")
    assert "subscriber_email_addresses" in budget and "subscriber_sns_topic_arns" not in budget


# Targets that use both variables: Terraform only checks a variable that the plan's graph reaches.
VALIDATION_TESTS = """
mock_provider "aws" {}
mock_provider "aws" {
  alias = "us_east_1"
}

variables {
  aws_account_id = "123456789012"
  domain         = "acme.io"
  github_repo    = "prodij/acme"
  alert_email    = "alerts@acme.io"
}

run "real_values_pass" {
  command = plan
  plan_options {
    target = [aws_iam_role.deploy, aws_sns_topic_subscription.email]
  }
}

run "owner_placeholder" {
  command = plan
  plan_options {
    target = [aws_iam_role.deploy, aws_sns_topic_subscription.email]
  }
  variables {
    github_repo = "owner/acme"
  }
  expect_failures = [var.github_repo]
}

run "not_org_and_name" {
  command = plan
  plan_options {
    target = [aws_iam_role.deploy, aws_sns_topic_subscription.email]
  }
  variables {
    github_repo = "acme"
  }
  expect_failures = [var.github_repo]
}

run "example_com" {
  command = plan
  plan_options {
    target = [aws_iam_role.deploy, aws_sns_topic_subscription.email]
  }
  variables {
    alert_email = "you@example.com"
  }
  expect_failures = [var.alert_email]
}

run "example_org" {
  command = plan
  plan_options {
    target = [aws_iam_role.deploy, aws_sns_topic_subscription.email]
  }
  variables {
    alert_email = "you@example.org"
  }
  expect_failures = [var.alert_email]
}
"""


@pytest.mark.slow
def test_terraform_refuses_placeholders(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    # Mocked providers: no credentials and no AWS. `validate` alone never evaluates these values.
    assert shutil.which("terraform"), "terraform is required for this test"
    infra = tmp_path / "infra"
    shutil.copytree(product_dir / "infra", infra)
    (infra / "placeholders.tftest.hcl").write_text(VALIDATION_TESTS)
    subprocess.run(["terraform", "init", "-backend=false", "-input=false"], cwd=infra, check=True, capture_output=True)
    result = subprocess.run(["terraform", "test"], cwd=infra, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_tfvars_still_holds_the_placeholders_terraform_refuses(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "terraform.tfvars").read_text()
    assert re.search(r'^github_repo\s*=\s*"owner/acme-reports"', text, re.M)
    assert re.search(r'^alert_email\s*=\s*"you@example\.com"', text, re.M)


def test_app_service_retries_and_a_failed_first_try_does_not_fail_user_data(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "user_data.sh.tftpl").read_text()
    for needed in ["Type=oneshot", "Restart=on-failure", "RestartSec=60", "StartLimitIntervalSec=0",
                   "SuccessExitStatus=45", "exit 45", "systemctl start --no-block app.service"]:
        assert needed in text, needed


def test_tfstate_is_ignored_and_nothing_committed_matches(product_dir: pathlib.Path) -> None:
    lines = (product_dir / ".gitignore").read_text().splitlines()
    assert "*.tfstate" in lines and "*.tfstate.*" in lines
    tracked = subprocess.run(["git", "ls-files", "template"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert not re.search(r"\.tfstate(\.|$)", tracked, re.M)


def test_db_init_passwords_never_reach_psql_arguments(product_dir: pathlib.Path) -> None:
    first_run = (product_dir / "deploy" / "first-run.sh").read_text()
    assert "app_password" not in first_run and "lago_password" not in first_run
    assert "\\getenv app_password APP_DB_PASSWORD" in (product_dir / "deploy" / "db-init.sql").read_text()


def test_no_false_eventbridge_claim(product_dir: pathlib.Path) -> None:
    assert "EventBridge" not in (product_dir / "jobs" / "schedules.yaml").read_text()


def test_agent_instructions_say_what_the_guard_misses(product_dir: pathlib.Path) -> None:
    text = (product_dir / "CLAUDE.md").read_text()
    assert "seatbelt" in text and "python infra.py destroy" in text
    assert "the guard enforces this" not in text


def test_product_ci_runs_when_deploy_changes(product_dir: pathlib.Path) -> None:
    assert '"deploy/**"' in (product_dir / ".github" / "workflows" / "scripts.yml").read_text()


def test_runbook_covers_day_two_limits(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "README.md").read_text()
    for needed in ["uploads the deploy files only", "must be committed", "5 Elastic IPs", "hosted zone",
                   "delete it first", "surviving product", "--force-recreate caddy", "no health check"]:
        assert needed in text, needed
    assert text.count("create_github_oidc_provider = true") >= 2
