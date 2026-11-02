"""The `make infra-*` commands (infra/README.md). AWS credentials come from AWS_PROFILE.

Nothing here prints a secret value. Every command checks the account first.
"""

import base64
import getpass
import hashlib
import hmac
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"
TFVARS = INFRA / "terraform.tfvars"
PLACEHOLDER_ACCOUNT = "000000000000"
# The same rules as the validation blocks in infra/variables.tf.
GITHUB_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+")
PLACEHOLDER_EMAIL = re.compile(r"[@.]example\.(com|org)$")

# Secret name -> generator command understood by make_env.generate.
SECRET_SPECS = {
    "ZITADEL_MASTERKEY": "openssl rand -hex 16",
    "LOGIN_SESSION_COOKIE_SECRET": "openssl rand -base64 32",
    "ZITADEL_ADMIN_PASSWORD": "password 24",
    "ZITADEL_DB_PASSWORD": "openssl rand -hex 24",
    "APP_DB_PASSWORD": "openssl rand -hex 24",
    "LAGO_DB_PASSWORD": "openssl rand -hex 24",
    "SECRET_KEY_BASE": "openssl rand -hex 64",
    "LAGO_RSA_PRIVATE_KEY": "openssl genrsa 2048 | openssl base64 -A",
    "LAGO_ENCRYPTION_PRIMARY_KEY": "openssl rand -hex 16",
    "LAGO_ENCRYPTION_DETERMINISTIC_KEY": "openssl rand -hex 16",
    "LAGO_ENCRYPTION_KEY_DERIVATION_SALT": "openssl rand -hex 16",
    "LAGO_API_KEY": "openssl rand -hex 24",
    "LAGO_ORG_USER_PASSWORD": "openssl rand -hex 16",
}


def read_tfvars(path: Path = TFVARS) -> dict[str, str]:
    pattern = re.compile(r'^\s*(\w+)\s*=\s*"([^"]*)"\s*$')
    return {m[1]: m[2] for line in path.read_text().splitlines() if (m := pattern.match(line))}


def check_account(actual: str, expected: str) -> None:
    if expected == PLACEHOLDER_ACCOUNT:
        raise SystemExit("set aws_account_id in infra/terraform.tfvars first")
    if actual != expected:
        raise SystemExit(f"AWS_PROFILE points at account {actual}, but this product is for {expected}")


def check_placeholders(tfvars: dict[str, str]) -> None:
    repo, email = tfvars.get("github_repo", ""), tfvars.get("alert_email", "")
    if not GITHUB_REPO.fullmatch(repo) or repo.lower().startswith("owner/"):
        raise SystemExit("set github_repo in infra/terraform.tfvars to this product's real org/name first")
    if PLACEHOLDER_EMAIL.search(email.lower()):
        raise SystemExit("set alert_email in infra/terraform.tfvars to a real address first")


def fill_secrets(existing: dict[str, str], generate: Callable[[str], str]) -> dict[str, str]:
    """Adds what's missing and never changes a value: a new Zitadel master key would break the product."""
    return {**{k: generate(c) for k, c in SECRET_SPECS.items() if k not in existing}, **existing}


def smtp_password(secret_key: str, region: str) -> str:
    """AWS's documented derivation of an SES SMTP password from an IAM secret key."""
    signature = ("AWS4" + secret_key).encode()
    for message in ["11111111", region, "ses", "aws4_request", "SendRawEmail"]:
        signature = hmac.new(signature, message.encode(), hashlib.sha256).digest()
    return base64.b64encode(b"\x04" + signature).decode()


def check_stripe_key(key: str) -> str:
    key = key.strip()
    if not key.startswith("sk_test_"):
        raise SystemExit("only Stripe test keys (sk_test_...) are accepted")
    return key


def session() -> Any:
    import boto3

    tfvars = read_tfvars()
    check_placeholders(tfvars)
    made = boto3.Session(region_name=tfvars["aws_region"])
    check_account(made.client("sts").get_caller_identity()["Account"], tfvars["aws_account_id"])
    return made


def state_bucket(tfvars: dict[str, str]) -> str:
    return f"{tfvars['slug']}-tfstate-{tfvars['aws_account_id']}"


def terraform_output(name: str) -> str:
    return subprocess.run(["terraform", "output", "-raw", name], cwd=INFRA, check=True,  # noqa: S603, S607
                          capture_output=True, text=True).stdout.strip()


def init() -> None:
    tfvars, aws = read_tfvars(), session()
    s3, bucket, region = aws.client("s3"), state_bucket(read_tfvars()), tfvars["aws_region"]
    if bucket not in [b["Name"] for b in s3.list_buckets()["Buckets"]]:
        config = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
        s3.create_bucket(Bucket=bucket, **config)
    # Every run, so a bucket that an earlier run left half set up is finished.
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    (INFRA / "backend.hcl").write_text(
        f'bucket = "{bucket}"\nkey = "terraform.tfstate"\nregion = "{region}"\nencrypt = true\nuse_lockfile = true\n')
    subprocess.run(["terraform", "init", "-backend-config=backend.hcl", "-input=false"], cwd=INFRA, check=True)  # noqa: S607


def read_secret(secrets: Any, secret_id: str) -> dict[str, str]:
    try:
        value: dict[str, str] = json.loads(secrets.get_secret_value(SecretId=secret_id)["SecretString"])
        return value
    except secrets.exceptions.ResourceNotFoundException as exc:
        if "AWSCURRENT" in str(exc):  # the container exists but has no value yet
            return {}
        raise SystemExit(f"{secret_id} doesn't exist: run make infra-apply first") from exc


def make_secrets() -> None:
    from make_env import generate

    tfvars, aws = read_tfvars(), session()
    secrets, slug = aws.client("secretsmanager"), tfvars["slug"]
    existing = read_secret(secrets, f"{slug}/app")
    filled = fill_secrets(existing, generate)
    if "SES_SMTP_USER" not in filled:
        key = aws.client("iam").create_access_key(UserName=f"{slug}-ses-smtp")["AccessKey"]
        filled["SES_SMTP_USER"] = key["AccessKeyId"]
        filled["SES_SMTP_PASSWORD"] = smtp_password(key["SecretAccessKey"], tfvars["aws_region"])
    if filled != existing:
        secrets.put_secret_value(SecretId=f"{slug}/app", SecretString=json.dumps(filled))
    print(f"{slug}/app holds {len(filled)} values ({len(filled) - len(existing)} new).")


def set_stripe_key() -> None:
    tfvars, aws = read_tfvars(), session()
    key = check_stripe_key(getpass.getpass("Stripe TEST secret key: "))
    secrets, slug = aws.client("secretsmanager"), tfvars["slug"]
    values = read_secret(secrets, f"{slug}/app")
    values["STRIPE_SECRET_KEY"] = key
    secrets.put_secret_value(SecretId=f"{slug}/app", SecretString=json.dumps(values))
    print("Saved. Run make infra-bootstrap to apply it.")


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=ROOT, check=True,  # noqa: S607
                          capture_output=True, text=True).stdout.strip()


def check_clean(porcelain: str) -> None:
    """An image tag is a commit and the bundle should match one, so uncommitted changes would ship unrecorded."""
    if porcelain.strip():
        raise SystemExit("the working tree has uncommitted changes; commit or stash them first, because image tags and the deploy files come from the commit")


def services_without_a_tag(ssm: Any, slug: str) -> list[str]:
    names = [f"/{slug}/tags/{service}" for service in SERVICES]
    found = {p["Name"] for p in ssm.get_parameters(Names=names)["Parameters"]}
    return [service for service, name in zip(SERVICES, names, strict=True) if name not in found]


def build_and_tag(aws: Any, ssm: Any, tfvars: dict[str, str], services: list[str]) -> str:
    slug, region, account, tag = tfvars["slug"], tfvars["aws_region"], tfvars["aws_account_id"], git_commit()
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"
    token = base64.b64decode(aws.client("ecr").get_authorization_token()["authorizationData"][0]["authorizationToken"]).decode().split(":", 1)[1]
    subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin", registry],  # noqa: S603, S607
                   input=token, text=True, check=True, capture_output=True)
    for service in services:
        image = f"{registry}/{slug}-{service}:{tag}"
        subprocess.run(["docker", "build", "--platform", "linux/amd64", "-t", image, service], cwd=ROOT, check=True)  # noqa: S603, S607
        subprocess.run(["docker", "push", image], check=True)  # noqa: S603, S607
        ssm.put_parameter(Name=f"/{slug}/tags/{service}", Value=tag, Type="String", Overwrite=True)
    return tag


def release() -> None:
    """The first release builds the images. After that the tags belong to the deploy workflows, which
    migrate, check health and roll back: moving them here would run this checkout's code without any of that."""
    check_clean(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,  # noqa: S607
                               capture_output=True, text=True).stdout)
    tfvars, aws = read_tfvars(), session()
    slug, account = tfvars["slug"], tfvars["aws_account_id"]
    ssm = aws.client("ssm")
    missing = services_without_a_tag(ssm, slug)
    tag = build_and_tag(aws, ssm, tfvars, missing) if missing else ""
    upload_bundle(aws.client("s3"), f"{slug}-deploy-{account}")
    if missing:
        print(f"Released {tag}.")
    else:
        print("Image tags already exist, so this uploaded the deploy files only and left images and tags alone. Images move through the deploy workflows.")


BUNDLE = ["docker-compose.aws.yml", "deploy", "scripts", "brand"]
SKIPPED_DIRS = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "rehearsal"}
SERVICES = ["backend", "jobs"]


def is_bundled(path: Path) -> bool:
    name = path.name
    return not (SKIPPED_DIRS.intersection(path.relative_to(ROOT).parts) or name == ".DS_Store" or name == ".env" or name.startswith(".env."))


def upload_bundle(s3: Any, bucket: str) -> None:
    """Deploy files as plain objects under current/, for `aws s3 sync` on the server."""
    for name in BUNDLE:
        path = ROOT / name
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file() and is_bundled(p)]
        for file in files:
            s3.upload_file(str(file), bucket, f"current/{file.relative_to(ROOT).as_posix()}")


def run_on_server(aws: Any, instance_id: str, command: str, timeout_s: int = 1800) -> str:
    ssm = aws.client("ssm")
    sent = ssm.send_command(InstanceIds=[instance_id], DocumentName="AWS-RunShellScript",
                            Parameters={"commands": [command], "executionTimeout": [str(timeout_s)]},
                            TimeoutSeconds=timeout_s)["Command"]["CommandId"]
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(5)
        try:
            result = ssm.get_command_invocation(CommandId=sent, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if result["Status"] in {"Success", "Failed", "Cancelled", "TimedOut"}:
            print(result["StandardOutputContent"])
            if result["Status"] != "Success":
                print(result["StandardErrorContent"], file=sys.stderr)
                raise SystemExit(f"on the server: {result['Status']}")
            return str(result["StandardOutputContent"])
    raise SystemExit("on the server: gave up waiting")


BOOTSTRAP_COMMAND = 'export HOME="${HOME:-/root}" PATH="$PATH:/usr/local/bin"; app-start && /opt/app/deploy/first-run.sh'


def bootstrap() -> None:
    aws = session()
    run_on_server(aws, terraform_output("server_instance_id"), BOOTSTRAP_COMMAND)


def delete_parameters(ssm: Any, slug: str) -> None:
    """Removes the SSM parameters Terraform doesn't own, so a redeploy of the slug starts clean."""
    names = [f"/{slug}/tags/{service}" for service in SERVICES] + [f"/{slug}/frontend"]
    ssm.delete_parameters(Names=names)


def owns_oidc_provider() -> bool:
    """The variable defaults to true, and read_tfvars only reads strings."""
    return not re.search(r"^\s*create_github_oidc_provider\s*=\s*false\b", TFVARS.read_text(), re.M)


OIDC_WARNING = """WARNING: this product owns the account's GitHub OIDC provider (create_github_oidc_provider is true).
Destroying it deletes the provider for every product in this account: their deploys fail at sign-in, and
their terraform plans fail looking it up. To recover, set create_github_oidc_provider = true on one
surviving product and run make infra-plan and make infra-apply there."""


def destroy() -> None:
    tfvars, aws = read_tfvars(), session()
    slug = tfvars["slug"]
    if owns_oidc_provider():
        print(OIDC_WARNING)
    print(f"This deletes {slug}, its database and its backups, in account {tfvars['aws_account_id']}.")
    if input(f"Type {slug} to continue: ") != slug:
        raise SystemExit("Not deleted.")
    for step in (["apply", "-var", "protect=false"], ["destroy", "-var", "protect=false"]):
        subprocess.run(["terraform", *step], cwd=INFRA, check=True)  # noqa: S603, S607
    delete_parameters(aws.client("ssm"), slug)
    bucket = aws.resource("s3").Bucket(state_bucket(tfvars))
    bucket.object_versions.delete()
    bucket.delete()
    print("Deleted, including the state bucket. Check AWS Billing in a day to confirm nothing is left.")


COMMANDS: dict[str, Callable[[], None]] = {
    "init": init, "secrets": make_secrets, "set-stripe-key": set_stripe_key,
    "release": release, "bootstrap": bootstrap, "destroy": destroy,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"usage: infra.py {{{'|'.join(COMMANDS)}}}")
    COMMANDS[sys.argv[1]]()
