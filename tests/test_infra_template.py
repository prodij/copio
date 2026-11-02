import json
import pathlib
import re
import shutil
import subprocess

import pytest
import yaml

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
    assert text.count("respond 403") == 2


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
