import pathlib
import re
import shutil
import subprocess

import pytest

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
