# Boilerplate milestone 2: AWS deployment, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A product generated from the template can be deployed to AWS by documented commands, live on HTTPS with sign-in working, survive losing its server, and be removed cleanly.

**Architecture:** One EC2 server per product runs `docker-compose.aws.yml` behind Caddy. RDS holds the databases, S3 holds files and a release bundle, CloudFront serves the frontend, and Secrets Manager holds secrets. A person applies Terraform; CI deploys app code through SSM Run Command.

**Tech Stack:** Terraform `~> 1.17`, AWS provider `~> 6.71`, Docker Compose v5.6.1, Caddy 2.11, Python 3.12 with uv and boto3, GitHub Actions with OIDC.

**Spec:** `docs/superpowers/specs/2026-11-01-boilerplate-milestone-2-aws-design.md`

## Global Constraints

- Every path below is relative to the repo root. Product files live under `template/`.
- Files ending `.jinja` are rendered by Copier. `.tf` files and workflows are not, so `{{ }}` and `${{ }}` in them are literal.
- Run `make dev` to generate `.dev/acme`, and run a product's tests there. Template-level tests run with `uv run pytest` at the repo root.
- Agents never run Terraform `apply` or `destroy`, never call a write command against AWS, and never read `.env`, `.bootstrap/` or a secret value. Task 13 is run by James.
- Terraform `~> 1.17`, AWS provider `~> 6.71`, with `.terraform.lock.hcl` committed.
- Every AWS resource name starts with `local.name`, which is the product slug.
- Stripe test keys only (`sk_test_`). No `stripe-cli` and no mock payment path in `docker-compose.aws.yml`.
- x86 server. Single-zone RDS Postgres 15. No NAT gateway. No SSH port.
- GitHub Actions are pinned to a full commit SHA with a `# vX.Y.Z` comment.
- This work is on `feat/aws-m2`, cut from `feat/two-products`, which contains PRs #7 (`feat/run-without-stripe`), #8 and #9. Its PR is stacked on #9.

## Facts verified while planning (2026-11-01)

| Fact | Source | Effect |
|---|---|---|
| `rds.force_ssl` defaults to on for Postgres 15+ | AWS RDS docs | All connection strings use `sslmode=require` |
| Creating `pg_partman` needs `rds_superuser`, which the RDS admin has | AWS RDS docs | `db-init.sql` creates it; Lago's own `IF NOT EXISTS` then does nothing |
| Lago's partman migrations skip silently if the extension is missing | `lago-api` v1.55.0 `db/migrate/20260109*` | `infra-doctor` checks it explicitly |
| Lago's S3 settings: `LAGO_USE_AWS_S3`, `LAGO_AWS_S3_REGION`, `LAGO_AWS_S3_BUCKET` | `lago` v1.55.0 Compose, `lago-api` `config/storage.yml` | Used in Task 6. **Using the instance role with the key variables unset is not yet proven**; Task 12 tests it |
| Zitadel `init` takes the admin login; `start-from-setup` doesn't need it | `zitadel` v4.20.0 `cmd/` | Admin password is used only once, in a one-shot service |
| Zitadel's first-instance SMTP settings | `zitadel` v4.20.0 `cmd/defaults.yaml` | Used in Task 6 |
| Pins: `setup-terraform` v4.0.1 `dfe3c3f8...`, `configure-aws-credentials` v6.3.0 `e1253824...`, Compose v5.6.1, Caddy 2.11 | GitHub, Docker Hub | Used below |

## Changes to the spec, made in Task 1

These came out of reading the code, and Task 1 edits the spec to match:

1. **`use_staging_certificates` is removed.** Containers call `https://auth.<domain>`, so they need a trusted certificate. Let's Encrypt allows 5 duplicate certificates a week, which is enough for the rebuild test.
2. **Empty `admin_cidrs` means Lago's UI is unavailable**, not reachable by port forward. The UI's browser code calls the public `lago-api.` host, so a tunnel doesn't help. To use it, add your IP and apply.
3. **`make infra-secrets` runs after the first apply**, because it fills secrets and an IAM user that Terraform creates.
4. **New command `make infra-release`** builds images and uploads a bundle of the deploy files. The server needs both before it can start.
5. **Zitadel gets the RDS admin login only once**, in a one-shot `zitadel-init` service.
6. **Containers can use the server's role**, so the instance metadata hop limit is 2.

## Review Focus

1. **Second product in one AWS account:** names don't clash, and the account-wide GitHub OIDC provider isn't created twice. Pinned in Task 2 and Task 5.
2. **Re-running `make infra-secrets`:** existing values stay. Rotating Zitadel's master key would break the product permanently. Pinned in Task 9.
3. **A replaced server:** it restores Zitadel's tokens and doesn't re-run first-time setup against a populated database. Pinned in Task 7.
4. **A bad deploy input or failed health check:** an unknown service or malformed tag is refused, and a failed release goes back to the previous version. Pinned in Task 7.
5. **Wrong AWS profile or a live Stripe key:** refused before anything is written. Pinned in Task 9.

## File map

```
template/
  infra/                     Terraform, one flat folder
    versions.tf variables.tf network.tf database.tf storage.tf secrets.tf email.tf
    server.tf monitoring.tf frontend.tf dns.tf ci.tf outputs.tf
    user_data.sh.tftpl       installs Docker, Compose, uv; starts the app at boot
    terraform.tfvars.jinja   a product's non-secret values
    README.md                the runbook
  docker-compose.aws.yml.jinja
  deploy/
    Caddyfile                HTTPS and routing
    db-init.sql              databases, roles, pg_partman
    start.sh                 runs at boot: fetch bundle, render .env, restore tokens, start
    first-run.sh             first deploy only: database setup, Zitadel init, bootstrap
    deploy.sh                one service: pull, migrate, start, health check, roll back
    rehearsal/               local stand-in for RDS, to test without AWS
  scripts/
    infra.py                 the infra-* commands
    infra_doctor.py          infra-doctor checks
    aws_state.py             bootstrap's AWS side: frontend values, saving tokens
    tests/test_infra.py tests/test_infra_doctor.py tests/test_aws_state.py tests/test_deploy_scripts.py
  .github/workflows/deploy-frontend.yml deploy-backend.yml deploy-jobs.yml
tests/test_infra_template.py template-level checks on a generated product
```

---

### Task 1: Agent guard and spec amendments

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- Spec edits also: set the Status line to approved; in §3 replace "so it needs upgrading first" wording only if it reads as a blocker (agents use a pinned binary; James upgrades for Task 13); in §6 say `make infra-plan` prints the account, and that `make infra-destroy` shows Terraform's plan and asks for confirmation at each stage instead of auto-approving; in §14 say this work is stacked on PRs #7 to #9.
- `run` is the helper's real name in `test_guard.py`. `.dev/acme` comes from root `make dev`.
- Guard fix round 1: `check_aws` blocks `secretsmanager` with `get-secret-value` or `batch-get-secret-value` anywhere in the non-dash words (global option values like `--profile p` bypassed the positional check); `TERRAFORM_WRITES` also has `test`, `refresh`, `workspace`; `gmake` is treated as `make`.

**Files:**
- Modify: `template/.claude/hooks/guard.py`, `template/.claude/hooks/test_guard.py`, `docs/superpowers/specs/2026-11-01-boilerplate-milestone-2-aws-design.md`

**Interfaces:**
- Produces: agents are blocked from Terraform writes and every `make infra-*` command except `infra-plan` and `infra-doctor`.

- [ ] **Step 1: Write the failing test.** Add to `test_guard.py`:

```python
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
```

Use the same helper the other tests in this file call; if it isn't named `run`, use its real name.

- [ ] **Step 2: Run it to see it fail.** `make dev && cd .dev/acme/.claude/hooks && uv run --no-project --with pytest pytest -q test_guard.py -k infrastructure`. Expected: the blocked cases FAIL.

- [ ] **Step 3: Implement.** In `guard.py`, add after `check_docker`:

```python
TERRAFORM_WRITES = {"apply", "destroy", "import", "state", "taint", "untaint", "force-unlock"}
MAKE_WRITES = {"infra-apply", "infra-destroy", "infra-secrets", "infra-set-stripe-key",
               "infra-release", "infra-bootstrap"}
INFRA_HINT = "a person runs this one; give them the command (see infra/README.md)"


def check_terraform(args: list[str]) -> None:
    words = [a for a in args if not a.startswith("-")]
    if words and words[0] in TERRAFORM_WRITES:
        raise Blocked(f"`terraform {words[0]}` changes real infrastructure; {INFRA_HINT}")


def check_make(args: list[str]) -> None:
    for word in args:
        if word in MAKE_WRITES:
            raise Blocked(f"`make {word}` changes real infrastructure; {INFRA_HINT}")


def check_aws(args: list[str]) -> None:
    words = [a for a in args if not a.startswith("-")]
    if words[:2] == ["secretsmanager", "get-secret-value"]:
        raise Blocked("reading secret values is not allowed")
```

In `check_command`, add before the final `return cwd`:

```python
    elif head in {"terraform", "tofu"}:
        check_terraform(args)
    elif head == "make":
        check_make(args)
    elif head == "aws":
        check_aws(args)
```

Update the module docstring's "Blocks" list to mention these.

- [ ] **Step 4: Run tests.** Same command without `-k`. Expected: all PASS.

- [ ] **Step 5: Amend the spec.** Make the six changes listed under "Changes to the spec" above: remove `use_staging_certificates` from §5 and the failure about rate limits if present; change the `admin_cidrs` paragraph in §4; reorder §6 to `infra-init`, `infra-plan`, `infra-apply`, `infra-secrets`, `infra-release`, `infra-bootstrap`, and add `infra-release` and `infra-set-stripe-key`; add the Zitadel one-shot and hop limit notes to §8 and §4.

- [ ] **Step 6: Commit.**

```bash
git add template/.claude/hooks docs/superpowers/specs/2026-11-01-boilerplate-milestone-2-aws-design.md
git commit -m "feat(infra): guard blocks agents from infrastructure writes; spec amendments"
```

---

### Task 2: Terraform foundation, network and template checks

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `test_tfvars_has_the_slug_and_no_secrets`: the file is aligned by `terraform fmt`, so match with `re.search(r'^slug\s*=\s*"acme-reports"', text, re.M)`.
- `NOT_RESOURCE_NAMES` must also hold `"Managed-CachingOptimized"`, `"/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"` and `"deploy"` (the SSM document's step name). These appear in Tasks 4 and 5. Add them now.
- `test_terraform_is_valid` passes at this task but fails during Tasks 3 and 4 by design, until Task 5 adds the resources they reference.

**Files:**
- Create: `template/infra/versions.tf`, `variables.tf`, `network.tf`, `outputs.tf`, `terraform.tfvars.jinja`, `tests/test_infra_template.py`
- Modify: `template/.gitignore`, `.github/workflows/template.yml`, `copier.yml` (only if `infra/` needs an exclude)

**Interfaces:**
- Produces: `local.name` (slug), `local.tags`, `var.aws_region`, `var.domain`, `var.route53_zone_id`, `var.github_repo`, `var.alert_email`, `var.monthly_budget_usd`, `var.admin_cidrs`, `var.instance_type`, `var.protect`, `var.create_github_oidc_provider`, `aws_vpc.main`, `aws_subnet.public` (list), `aws_subnet.private` (list), provider alias `aws.us_east_1`. Every later Terraform task uses these.

- [ ] **Step 1: Write the failing test.** Create `tests/test_infra_template.py`:

```python
import pathlib
import re
import shutil
import subprocess

import pytest

# Attribute values that aren't AWS resource names.
NOT_RESOURCE_NAMES = {"image-id", "Product", "TagKeyValue"}


def tf_files(product_dir: pathlib.Path) -> list[pathlib.Path]:
    return sorted((product_dir / "infra").glob("*.tf"))


def test_tfvars_has_the_slug_and_no_secrets(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "terraform.tfvars").read_text()
    assert 'slug = "acme-reports"' in text
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
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q`. Expected: FAIL, `terraform.tfvars` not found.

- [ ] **Step 3: Implement.**

`template/infra/versions.tf`:

```hcl
terraform {
  required_version = "~> 1.17"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.71"
    }
  }
  # `make infra-init` writes backend.hcl with this product's state bucket.
  backend "s3" {}
}

locals {
  name = var.slug
  tags = { Product = var.slug }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags { tags = local.tags }
}

# CloudFront only accepts certificates from us-east-1.
provider "aws" {
  alias               = "us_east_1"
  region              = "us-east-1"
  allowed_account_ids = [var.aws_account_id]
  default_tags { tags = local.tags }
}
```

`template/infra/variables.tf`:

```hcl
variable "slug" { type = string }
variable "aws_account_id" { type = string }
variable "aws_region" { type = string }
variable "domain" {
  type        = string
  description = "Parent domain; the app is app.<domain>"
}
variable "route53_zone_id" { type = string }
variable "github_repo" {
  type        = string
  description = "owner/name of the repo allowed to deploy"
}
variable "alert_email" { type = string }
variable "monthly_budget_usd" {
  type    = number
  default = 150
}
variable "admin_cidrs" {
  type        = list(string)
  description = "Who can open Lago's UI. Empty means nobody."
  default     = []
}
variable "instance_type" {
  type    = string
  default = "t3.large"
}
variable "protect" {
  type        = bool
  description = "Deletion protection and final snapshots. `make infra-destroy` switches this off first."
  default     = true
}
variable "create_github_oidc_provider" {
  type        = bool
  description = "An account has one GitHub OIDC provider. Set false for the second product in an account."
  default     = true
}
```

`template/infra/network.tf`:

```hcl
data "aws_availability_zones" "available" { state = "available" }

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = local.name }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.name}-public-${count.index}" }
}

# RDS requires subnets in two zones, even for a single-zone instance. No route to the internet.
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags              = { Name = "${local.name}-private-${count.index}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
```

`template/infra/outputs.tf`:

```hcl
output "aws_region" { value = var.aws_region }
```

`template/infra/terraform.tfvars.jinja`:

```hcl
# Non-secret values for this product. See README.md in this folder.
slug               = "{{ product_slug }}"
aws_account_id     = "000000000000"
aws_region         = "us-west-2"
domain             = "example.com"
route53_zone_id    = "Z0000000000000000000"
github_repo        = "owner/{{ product_slug }}"
alert_email        = "you@example.com"
monthly_budget_usd = 150
admin_cidrs        = []
```

Append to `template/.gitignore`:

```
infra/.terraform/
infra/tfplan
infra/backend.hcl
```

In `.github/workflows/template.yml`, add this step to `generated-check` before `uv sync --locked`:

```yaml
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with: {terraform_version: "1.17.1", terraform_wrapper: false}
```

- [ ] **Step 4: Run tests.** Install Terraform 1.17 locally if needed. `uv run pytest tests/test_infra_template.py -q` and `uv run pytest tests/test_infra_template.py -q -m slow`. Expected: PASS. If the `slow` marker needs `-m slow` to run in this repo, follow how `tests/test_generated_checks.py` does it.

- [ ] **Step 5: Commit the lock file too.** Generate `template/infra/.terraform.lock.hcl` with `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64` in a generated copy, copy it into `template/infra/`, and commit:

```bash
git add template/infra template/.gitignore tests/test_infra_template.py .github/workflows/template.yml
git commit -m "feat(infra): Terraform foundation, network and template checks"
```

---

### Task 3: Database, storage, secrets and email

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `aws_iam_user.ses_smtp` gets `force_destroy = true`. `make infra-secrets` creates its access key outside Terraform, and without this `terraform destroy` fails with DeleteConflict (spec §1 item 5). Assert it in a test.
- Add an `aws_route53_record.ses_verification` TXT record: name `_amazonses.${var.domain}`, records `[aws_ses_domain_identity.main.verification_token]`, ttl 600, and add it to the verification resource's `depends_on`. `aws_ses_domain_identity_verification` waits on the identity's verification status, and this TXT record is the provider's documented way to reach it.

**Files:**
- Create: `template/infra/database.tf`, `storage.tf`, `secrets.tf`, `email.tf`
- Modify: `template/infra/outputs.tf`

**Interfaces:**
- Consumes: Task 2's locals and variables; `aws_security_group.server` from Task 4 (Terraform resolves order; the validate test runs after Task 4).
- Produces: `aws_db_instance.main` (with `.master_user_secret[0].secret_arn`), `aws_s3_bucket.data`, `aws_s3_bucket.deploy`, `aws_ecr_repository.backend`, `aws_ecr_repository.jobs`, `aws_secretsmanager_secret.app` (`<slug>/app`), `aws_secretsmanager_secret.bootstrap` (`<slug>/bootstrap`), `aws_iam_user.ses_smtp` (`<slug>-ses-smtp`), SES identity.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_infra_template.py`:

```python
def test_database_is_private_protected_and_backed_up(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "database.tf").read_text()
    assert "publicly_accessible" in text and "publicly_accessible     = false" in text
    assert "manage_master_user_password = true" in text
    assert "deletion_protection" in text and "var.protect" in text
    assert "backup_retention_period = 7" in text
    assert 'engine_version          = "15"' in text


def test_terraform_never_holds_secret_values(product_dir: pathlib.Path) -> None:
    text = "\n".join(p.read_text() for p in tf_files(product_dir))
    assert "aws_secretsmanager_secret_version" not in text
    assert "aws_iam_access_key" not in text
    assert "random_password" not in text
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q -k "database or secret"`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/infra/database.tf`:

```hcl
resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "database" {
  name   = "${local.name}-database"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.server.id]
  }
}

resource "aws_db_instance" "main" {
  identifier                  = local.name
  engine                      = "postgres"
  engine_version              = "15"
  instance_class              = "db.t4g.small"
  allocated_storage           = 20
  max_allocated_storage       = 100
  storage_type                = "gp3"
  storage_encrypted           = true
  username                    = "dbadmin"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  publicly_accessible         = false
  multi_az                    = false
  backup_retention_period     = 7
  deletion_protection         = var.protect
  skip_final_snapshot         = !var.protect
  final_snapshot_identifier   = var.protect ? "${local.name}-final" : null
  delete_automated_backups    = !var.protect
  auto_minor_version_upgrade  = true
}
```

Align assignment spacing with `terraform fmt`, then correct the test strings in Step 1 to match what `fmt` produces.

`template/infra/storage.tf`:

```hcl
# Jobs' raw data and Lago's files.
resource "aws_s3_bucket" "data" {
  bucket        = "${local.name}-data-${var.aws_account_id}"
  force_destroy = !var.protect
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# The bundle of deploy files that `make infra-release` uploads and the server fetches.
resource "aws_s3_bucket" "deploy" {
  bucket        = "${local.name}-deploy-${var.aws_account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "deploy" {
  bucket                  = aws_s3_bucket.deploy.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_ecr_repository" "backend" {
  name         = "${local.name}-backend"
  force_delete = true
}

resource "aws_ecr_repository" "jobs" {
  name         = "${local.name}-jobs"
  force_delete = true
}

resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each   = { backend = aws_ecr_repository.backend.name, jobs = aws_ecr_repository.jobs.name }
  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 20 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }
      action       = { type = "expire" }
    }]
  })
}
```

`template/infra/secrets.tf`:

```hcl
# Empty containers. `make infra-secrets` fills `app`; bootstrap fills `bootstrap` with Zitadel's
# tokens. Terraform never sees the values, so they stay out of state.
resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name}/app"
  recovery_window_in_days = var.protect ? 7 : 0
}

resource "aws_secretsmanager_secret" "bootstrap" {
  name                    = "${local.name}/bootstrap"
  recovery_window_in_days = var.protect ? 7 : 0
}
```

`template/infra/email.tf`:

```hcl
resource "aws_ses_domain_identity" "main" {
  domain = var.domain
}

resource "aws_ses_domain_dkim" "main" {
  domain = aws_ses_domain_identity.main.domain
}

resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = var.route53_zone_id
  name    = "${aws_ses_domain_dkim.main.dkim_tokens[count.index]}._domainkey.${var.domain}"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_ses_domain_dkim.main.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_ses_domain_identity_verification" "main" {
  domain     = aws_ses_domain_identity.main.id
  depends_on = [aws_route53_record.ses_dkim]
}

# `make infra-secrets` creates this user's key and derives the SMTP password.
resource "aws_iam_user" "ses_smtp" {
  name = "${local.name}-ses-smtp"
}

resource "aws_iam_user_policy" "ses_smtp" {
  name = "${local.name}-send-email"
  user = aws_iam_user.ses_smtp.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "ses:SendRawEmail"
      Resource = "*"
      Condition = { StringEquals = { "ses:FromAddress" = "no-reply@${var.domain}" } }
    }]
  })
}
```

Two products sharing a domain would clash on the SES identity. That isn't a supported setup, because each product has its own domain.

- [ ] **Step 4: Run tests.** `uv run pytest tests/test_infra_template.py -q -k "database or secret or named"`. Expected: PASS. Terraform validate runs after Task 4.

- [ ] **Step 5: Commit.**

```bash
git add template/infra tests/test_infra_template.py
git commit -m "feat(infra): RDS, S3, ECR, secret containers and SES"
```

---

### Task 4: Server, DNS and alarms

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- In `user_data.sh.tftpl`, `aws s3 sync` also gets `--exclude "scripts/.venv/*"`, or every boot deletes and rebuilds the scripts' environment.
- `ami = data.aws_ssm_parameter.al2023.insecure_value`: `.value` is sensitive, which hides the AMI in the plan a person has to read.

**Files:**
- Create: `template/infra/server.tf`, `user_data.sh.tftpl`, `monitoring.tf`, `dns.tf`
- Modify: `template/infra/outputs.tf`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces: `aws_instance.server`, `aws_eip.server`, `aws_security_group.server`, `aws_iam_role.server`, SSM parameter `/<slug>/config` holding a JSON object with `DOMAIN`, `AWS_REGION`, `SLUG`, `DB_HOST`, `DATA_BUCKET`, `DEPLOY_BUCKET`, `ECR_REGISTRY`, `ADMIN_CIDRS` (space separated), `ACME_EMAIL`, `DB_ADMIN_SECRET_ARN`, `FRONTEND_BUCKET`, `DISTRIBUTION_ID`, `SMTP_HOST`, `INSTANCE_ID`. Tasks 6 to 10 read those exact keys.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_infra_template.py`:

```python
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
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q -k server`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/infra/server.tf`:

```hcl
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "server" {
  name   = "${local.name}-server"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "server" {
  name = "${local.name}-server"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.server.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.server.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "server" {
  name = "${local.name}-server"
  role = aws_iam_role.server.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.app.arn, aws_secretsmanager_secret.bootstrap.arn, aws_db_instance.main.master_user_secret[0].secret_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:PutSecretValue"]
        Resource = [aws_secretsmanager_secret.bootstrap.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${local.name}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:PutParameter"]
        Resource = ["arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${local.name}/frontend", "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${local.name}/tags/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.deploy.arn, "${aws_s3_bucket.deploy.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = [aws_ecr_repository.backend.arn, aws_ecr_repository.jobs.arn]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "server" {
  name = "${local.name}-server"
  role = aws_iam_role.server.name
}

resource "aws_instance" "server" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.server.id]
  iam_instance_profile   = aws_iam_instance_profile.server.name
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    slug   = local.name
    region = var.aws_region
    bucket = aws_s3_bucket.deploy.bucket
  })
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
  root_block_device {
    volume_type = "gp3"
    volume_size = 40
    encrypted   = true
  }
  tags = { Name = "${local.name}-server" }
  lifecycle {
    # A new AMI or start script mustn't replace the server on an unrelated apply.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip" "server" {
  instance = aws_instance.server.id
  domain   = "vpc"
}

resource "aws_ssm_parameter" "config" {
  name = "/${local.name}/config"
  type = "String"
  value = jsonencode({
    SLUG                = local.name
    DOMAIN              = var.domain
    AWS_REGION          = var.aws_region
    DB_HOST             = aws_db_instance.main.address
    DATA_BUCKET         = aws_s3_bucket.data.bucket
    DEPLOY_BUCKET       = aws_s3_bucket.deploy.bucket
    ECR_REGISTRY        = split("/", aws_ecr_repository.backend.repository_url)[0]
    ADMIN_CIDRS         = join(" ", var.admin_cidrs)
    ACME_EMAIL          = var.alert_email
    DB_ADMIN_SECRET_ARN = aws_db_instance.main.master_user_secret[0].secret_arn
    FRONTEND_BUCKET     = aws_s3_bucket.frontend.bucket
    DISTRIBUTION_ID     = aws_cloudfront_distribution.frontend.id
    SMTP_HOST           = "email-smtp.${var.aws_region}.amazonaws.com:587"
    INSTANCE_ID         = aws_instance.server.id
  })
}
```

`template/infra/user_data.sh.tftpl`. Terraform's `templatefile` treats `$${` as a literal `${`:

```bash
#!/bin/bash
set -euo pipefail
dnf install -y docker jq amazon-cloudwatch-agent
mkdir -p /usr/libexec/docker/cli-plugins
curl -fsSL -o /usr/libexec/docker/cli-plugins/docker-compose \
  https://github.com/docker/compose/releases/download/v5.6.1/docker-compose-linux-x86_64
chmod +x /usr/libexec/docker/cli-plugins/docker-compose
curl -fsSL https://astral.sh/uv/0.10.2/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

cat > /etc/docker/daemon.json <<'JSON'
{"log-driver": "json-file", "log-opts": {"max-size": "20m", "max-file": "5"}}
JSON
systemctl enable --now docker

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'JSON'
{"metrics": {"append_dimensions": {"InstanceId": "$${aws:InstanceId}"},
  "metrics_collected": {"disk": {"resources": ["/"], "measurement": ["used_percent"]},
                        "mem": {"measurement": ["used_percent"]}}}}
JSON
systemctl enable --now amazon-cloudwatch-agent

cat > /etc/app.env <<ENV
SLUG=${slug}
AWS_REGION=${region}
DEPLOY_BUCKET=${bucket}
ENV

cat > /usr/local/bin/app-start <<'SCRIPT'
#!/bin/bash
set -euo pipefail
source /etc/app.env
mkdir -p /opt/app
aws s3 sync --delete --exclude ".env" --exclude ".bootstrap/*" "s3://$DEPLOY_BUCKET/current/" /opt/app/ --region "$AWS_REGION"
chmod +x /opt/app/deploy/*.sh
exec /opt/app/deploy/start.sh
SCRIPT
chmod +x /usr/local/bin/app-start

cat > /etc/systemd/system/app.service <<'UNIT'
[Unit]
Description=Product stack
After=docker.service network-online.target
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/app-start
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable app.service
# Before the first release there's no bundle yet: start.sh isn't there, and this exits harmlessly.
systemctl start app.service || echo "app not started: run make infra-release"
```

`template/infra/dns.tf`:

```hcl
resource "aws_route53_record" "server" {
  for_each = toset(["auth", "api", "lago", "lago-api"])
  zone_id  = var.route53_zone_id
  name     = "${each.key}.${var.domain}"
  type     = "A"
  ttl      = 300
  records  = [aws_eip.server.public_ip]
}
```

`template/infra/monitoring.tf`:

```hcl
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "server_recover" {
  alarm_name          = "${local.name}-server-recover"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_System"
  dimensions          = { InstanceId = aws_instance.server.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = ["arn:aws:automate:${var.aws_region}:ec2:recover", aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "server_unhealthy" {
  alarm_name          = "${local.name}-server-unhealthy"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = aws_instance.server.id }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "disk" {
  alarm_name          = "${local.name}-disk"
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  dimensions          = { InstanceId = aws_instance.server.id, path = "/", device = "nvme0n1p1", fstype = "xfs" }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${local.name}-database-storage"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 2147483648
  comparison_operator = "LessThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Tag-filtered budgets only count once the `Product` cost allocation tag is activated (README).
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:Product$%s", local.name)]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
```

`format` is used in `cost_filter.values` because the value needs a literal `$` straight before the slug, which string interpolation can't write cleanly.

Add to `outputs.tf`:

```hcl
output "server_instance_id" { value = aws_instance.server.id }
output "server_ip" { value = aws_eip.server.public_ip }
```

- [ ] **Step 4: Run tests.** `uv run pytest tests/test_infra_template.py -q -k "server or named"`. Expected: PASS. Validate runs after Task 5 creates the frontend resources.

- [ ] **Step 5: Commit.**

```bash
git add template/infra tests/test_infra_template.py
git commit -m "feat(infra): server, DNS, alarms and budget"
```

---

### Task 5: Frontend hosting and CI access

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- Three fixes to Task 4's files, from its review. `user_data.sh.tftpl`: replace `systemctl enable --now amazon-cloudwatch-agent` with `/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`, because the agent ignores that file until told to load it, and the disk alarm would never fire. Add `mkdir -p /etc/docker` before writing `daemon.json`. `server.tf`: `aws_eip.server` gets `depends_on = [aws_internet_gateway.main]`, as the provider's docs advise.
- `test_second_product_can_skip_the_oidc_provider`: `terraform fmt` aligns `count`, so match with `re.search(r"count\s*=\s*var\.create_github_oidc_provider \? 1 : 0", text)`.
- Ran it: `terraform validate` passed first time with the brief's code unchanged; no fixes were needed across `template/infra/`. The Task 4 fixes and the `count` regex were applied as above, and `terraform fmt` re-aligned `server.tf`'s `aws_eip` arguments.

**Files:**
- Create: `template/infra/frontend.tf`, `ci.tf`
- Modify: `template/infra/outputs.tf`

**Interfaces:**
- Consumes: Tasks 2 to 4.
- Produces: `aws_s3_bucket.frontend`, `aws_cloudfront_distribution.frontend`, role `<slug>-deploy`, SSM document `<slug>-deploy` with parameters `service` (`backend` or `jobs`) and `tag`, and output `deploy_role_arn`.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_infra_template.py`:

```python
def test_deploy_role_is_limited_to_main_and_has_no_terraform_or_secrets(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "ci.tf").read_text()
    assert "repo:${var.github_repo}:ref:refs/heads/main" in text
    assert "secretsmanager" not in text
    assert "AdministratorAccess" not in text
    assert 'allowedValues = ["backend", "jobs"]' in text


def test_second_product_can_skip_the_oidc_provider(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "ci.tf").read_text()
    assert "count = var.create_github_oidc_provider ? 1 : 0" in text
    assert 'data "aws_iam_openid_connect_provider" "github"' in text
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q -k "deploy_role or oidc"`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/infra/frontend.tf`:

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name}-frontend-${var.aws_account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_acm_certificate" "frontend" {
  provider          = aws.us_east_1
  domain_name       = "app.${var.domain}"
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "certificate" {
  for_each = { for o in aws_acm_certificate.frontend.domain_validation_options : o.domain_name => o }
  zone_id  = var.route53_zone_id
  name     = each.value.resource_record_name
  type     = each.value.resource_record_type
  ttl      = 300
  records  = [each.value.resource_record_value]
}

resource "aws_acm_certificate_validation" "frontend" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.frontend.arn
  validation_record_fqdns = [for r in aws_route53_record.certificate : r.fqdn]
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = local.name
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  aliases             = ["app.${var.domain}"]
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }
  default_cache_behavior {
    target_origin_id       = "frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
    compress               = true
  }
  # The frontend routes in the browser, so unknown paths serve the app.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.frontend.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn } }
    }]
  })
}

resource "aws_route53_record" "app" {
  zone_id = var.route53_zone_id
  name    = "app.${var.domain}"
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}
```

`template/infra/ci.tf`:

```hcl
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  github_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_role" "deploy" {
  name = "${local.name}-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = local.github_provider_arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_ssm_document" "deploy" {
  name          = "${local.name}-deploy"
  document_type = "Command"
  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy one service"
    parameters = {
      service = { type = "String", allowedValues = ["backend", "jobs"] }
      tag     = { type = "String", allowedPattern = "^[0-9a-f]{7,40}$" }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "deploy"
      inputs = { runCommand = ["/opt/app/deploy/deploy.sh {{ service }} {{ tag }}"] }
    }]
  })
}

resource "aws_iam_role_policy" "deploy" {
  name = "${local.name}-deploy"
  role = aws_iam_role.deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      {
        Effect   = "Allow"
        Action   = ["ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart", "ecr:BatchGetImage"]
        Resource = [aws_ecr_repository.backend.arn, aws_ecr_repository.jobs.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.frontend.arn, "${aws_s3_bucket.frontend.arn}/*"]
      },
      { Effect = "Allow", Action = ["cloudfront:CreateInvalidation"], Resource = aws_cloudfront_distribution.frontend.arn },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${local.name}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = [aws_ssm_document.deploy.arn, aws_instance.server.arn]
      },
      { Effect = "Allow", Action = ["ssm:GetCommandInvocation"], Resource = "*" },
    ]
  })
}
```

Add to `outputs.tf`:

```hcl
output "deploy_role_arn" { value = aws_iam_role.deploy.arn }
```

The test's `{{ service }}` line is safe because `.tf` files aren't rendered by Copier. Confirm with `grep -c '{{ service }}' .dev/acme/infra/ci.tf` after `make dev`.

- [ ] **Step 4: Run the full Terraform check.** `uv run pytest tests/test_infra_template.py -q` then `uv run pytest tests/test_infra_template.py -q -m slow`. Expected: PASS, including `terraform validate`.

- [ ] **Step 5: Commit.**

```bash
git add template/infra tests/test_infra_template.py
git commit -m "feat(infra): CloudFront frontend, GitHub OIDC deploy role and deploy document"
```

---

### Task 6: AWS Compose file and Caddy

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `LAGO_ORG_NAME`, `ZITADEL_FIRSTINSTANCE_ORG_NAME`, and `ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_FROMNAME` use `{{ product_name | tojson }}` with no surrounding quotes, like `docker-compose.yml.jinja`.
- `zitadel-login` also gets `CUSTOM_REQUEST_HEADERS: x-zitadel-public-host:auth.${DOMAIN}`, which PR #9 added locally so logo and font URLs point at the right host.
- Do not add `LAGO_DISABLE_SSL`. Checked in `getlago/api:v1.55.0` `config/environments/production.rb`: `assume_ssl` is on unless that's set and `force_ssl` is false, so plain http on the Compose network isn't redirected and generated URLs stay https. Say so in a one-line comment in the file.
- Spec §10 requires `docker compose config` on this file on every PR. Add a fast test: `docker compose -f docker-compose.aws.yml --profile setup config --quiet --no-interpolate` in `product_dir`, returning 0.

**Files:**
- Create: `template/docker-compose.aws.yml.jinja`, `template/deploy/Caddyfile`, `template/deploy/db-init.sql`
- Test: `tests/test_infra_template.py`

**Interfaces:**
- Consumes: `.env` keys rendered by Task 7: the config keys from Task 4 plus `BACKEND_TAG`, `JOBS_TAG`, and the secrets in Task 9's `SECRET_SPECS`.
- Produces: services `caddy`, `redis`, `zitadel-init` (profile `setup`), `zitadel-api`, `zitadel-login`, `lago-migrate`, `lago-api`, `lago-worker`, `lago-clock`, `lago-front`, `lago-pdf`, `backend`, `jobs`. Loopback ports: `lago-api` on 3000, `backend` on 8000.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_infra_template.py`:

```python
import yaml  # move to the top of the file


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
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q -k "aws_compose or caddy or database_connections or setup_service or only_caddy"`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/docker-compose.aws.yml.jinja`:

```yaml
# The product on AWS. deploy/start.sh renders .env from Secrets Manager and SSM.
# Local development uses docker-compose.yml.
name: {{ product_slug }}

x-restart: &restart
  restart: unless-stopped

x-lago-env: &lago-env
  DATABASE_URL: postgresql://lago:${LAGO_DB_PASSWORD}@${DB_HOST}:5432/lago?sslmode=require
  REDIS_URL: redis://redis:6379
  LAGO_REDIS_CACHE_URL: redis://redis:6379
  SECRET_KEY_BASE: ${SECRET_KEY_BASE}
  LAGO_RSA_PRIVATE_KEY: ${LAGO_RSA_PRIVATE_KEY}
  LAGO_ENCRYPTION_PRIMARY_KEY: ${LAGO_ENCRYPTION_PRIMARY_KEY}
  LAGO_ENCRYPTION_DETERMINISTIC_KEY: ${LAGO_ENCRYPTION_DETERMINISTIC_KEY}
  LAGO_ENCRYPTION_KEY_DERIVATION_SALT: ${LAGO_ENCRYPTION_KEY_DERIVATION_SALT}
  LAGO_API_URL: https://lago-api.${DOMAIN}
  LAGO_FRONT_URL: https://lago.${DOMAIN}
  LAGO_PDF_URL: http://lago-pdf:3000
  LAGO_WEBHOOK_ALLOW_PRIVATE_URLS: "true"  # Lago calls the backend over the Compose network
  LAGO_DISABLE_SEGMENT: "true"
  LAGO_DISABLE_SIGNUP: "true"
  LAGO_CREATE_ORG: "true"
  LAGO_ORG_NAME: "{{ product_name }}"
  LAGO_ORG_USER_EMAIL: admin@${DOMAIN}
  LAGO_ORG_USER_PASSWORD: ${LAGO_ORG_USER_PASSWORD}
  LAGO_ORG_API_KEY: ${LAGO_API_KEY}
  # Files go to S3 using the server's role: the LAGO_AWS_S3_*_KEY variables stay unset.
  LAGO_USE_AWS_S3: "true"
  LAGO_AWS_S3_REGION: ${AWS_REGION}
  LAGO_AWS_S3_BUCKET: ${DATA_BUCKET}
  RAILS_ENV: production
  RAILS_LOG_TO_STDOUT: "true"

x-zitadel-env: &zitadel-env
  ZITADEL_MASTERKEY: ${ZITADEL_MASTERKEY}
  ZITADEL_PORT: 8080
  ZITADEL_EXTERNALDOMAIN: auth.${DOMAIN}
  ZITADEL_EXTERNALPORT: 443
  ZITADEL_EXTERNALSECURE: "true"
  ZITADEL_TLS_ENABLED: "false"  # Caddy ends TLS; also read by the `zitadel ready` healthcheck
  ZITADEL_DATABASE_POSTGRES_HOST: ${DB_HOST}
  ZITADEL_DATABASE_POSTGRES_PORT: 5432
  ZITADEL_DATABASE_POSTGRES_DATABASE: zitadel
  ZITADEL_DATABASE_POSTGRES_USER_USERNAME: zitadel
  ZITADEL_DATABASE_POSTGRES_USER_PASSWORD: ${ZITADEL_DB_PASSWORD}
  ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE: require

services:
  caddy:
    <<: *restart
    image: caddy:2.11-alpine
    environment:
      DOMAIN: ${DOMAIN}
      ACME_EMAIL: ${ACME_EMAIL}
      ADMIN_CIDRS: ${ADMIN_CIDRS:-192.0.2.1/32}  # TEST-NET: matches nobody
      CADDY_GLOBAL_OPTIONS: ${CADDY_GLOBAL_OPTIONS:-}
    volumes:
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    ports: ["80:80", "443:443"]

  redis:
    <<: *restart
    image: redis:7-alpine
    healthcheck: {test: ["CMD", "redis-cli", "ping"], interval: 3s, retries: 30}

  # First deploy only. Creates Zitadel's role, database and schema with the RDS admin login.
  zitadel-init:
    image: ghcr.io/zitadel/zitadel:v4.20.0
    profiles: [setup]
    command: init
    environment:
      <<: *zitadel-env
      ZITADEL_DATABASE_POSTGRES_ADMIN_USERNAME: ${DB_ADMIN_USER:-dbadmin}
      ZITADEL_DATABASE_POSTGRES_ADMIN_PASSWORD: ${DB_ADMIN_PASSWORD:-}
      ZITADEL_DATABASE_POSTGRES_ADMIN_EXISTINGDATABASE: postgres
      ZITADEL_DATABASE_POSTGRES_ADMIN_SSL_MODE: require

  zitadel-api:
    <<: *restart
    image: ghcr.io/zitadel/zitadel:v4.20.0
    user: "1000:1000"  # start.sh gives .bootstrap to this user
    command: start-from-setup --masterkeyFromEnv --tlsMode external
    environment:
      <<: *zitadel-env
      ZITADEL_FIRSTINSTANCE_ORG_NAME: "{{ product_name }}"
      ZITADEL_FIRSTINSTANCE_ORG_HUMAN_USERNAME: admin@${DOMAIN}
      ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD: ${ZITADEL_ADMIN_PASSWORD}
      ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED: "false"
      ZITADEL_FIRSTINSTANCE_PATPATH: /zitadel/bootstrap/admin.pat
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_USERNAME: bootstrap-admin
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_NAME: Bootstrap admin
      ZITADEL_FIRSTINSTANCE_ORG_MACHINE_PAT_EXPIRATIONDATE: "2099-01-01T00:00:00Z"
      ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH: /zitadel/bootstrap/login-client.pat
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_USERNAME: login-client
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_NAME: Login client
      ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_PAT_EXPIRATIONDATE: "2099-01-01T00:00:00Z"
      ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED: "true"
      ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_BASEURI: https://auth.${DOMAIN}/ui/v2/login/
      ZITADEL_OIDC_DEFAULTLOGINURLV2: https://auth.${DOMAIN}/ui/v2/login/login?authRequest=
      ZITADEL_OIDC_DEFAULTLOGOUTURLV2: https://auth.${DOMAIN}/ui/v2/login/logout?post_logout_redirect=
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_HOST: ${SMTP_HOST}
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_USER: ${SES_SMTP_USER}
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_PASSWORD: ${SES_SMTP_PASSWORD}
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_TLS: "true"
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_FROM: no-reply@${DOMAIN}
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_FROMNAME: "{{ product_name }}"
    volumes: [./.bootstrap/zitadel:/zitadel/bootstrap]
    healthcheck: {test: ["CMD", "/app/zitadel", "ready"], interval: 5s, retries: 60, start_period: 10s}

  zitadel-login:
    <<: *restart
    image: ghcr.io/zitadel/zitadel-login:v4.20.0
    environment:
      ZITADEL_API_URL: https://auth.${DOMAIN}
      ZITADEL_SERVICE_USER_TOKEN_FILE: /zitadel/bootstrap/login-client.pat
      ZITADEL_SESSION_COOKIE_SECRET: ${LOGIN_SESSION_COOKIE_SECRET}
      EMAIL_VERIFICATION: "true"
    volumes: [./.bootstrap/zitadel:/zitadel/bootstrap:ro]
    depends_on: {zitadel-api: {condition: service_healthy}}

  lago-migrate:
    image: getlago/api:v1.55.0
    command: ["./scripts/migrate.sh"]
    environment: *lago-env
    depends_on: {redis: {condition: service_healthy}}

  lago-api:
    <<: *restart
    image: getlago/api:v1.55.0
    command: ["./scripts/start.api.sh"]
    environment: *lago-env
    ports: ["127.0.0.1:3000:3000"]
    depends_on: {lago-migrate: {condition: service_completed_successfully}}
    healthcheck:
      test: ["CMD-SHELL", "curl -fs http://localhost:3000/health || exit 1"]
      interval: 5s
      retries: 60

  lago-worker:
    <<: *restart
    image: getlago/api:v1.55.0
    command: ["./scripts/start.worker.sh"]
    environment: *lago-env
    depends_on: {lago-migrate: {condition: service_completed_successfully}}

  lago-clock:
    <<: *restart
    image: getlago/api:v1.55.0
    command: ["./scripts/start.clock.sh"]
    environment: *lago-env
    depends_on: {lago-migrate: {condition: service_completed_successfully}}

  lago-front:
    <<: *restart
    image: getlago/front:v1.55.0
    environment:
      API_URL: https://lago-api.${DOMAIN}
      APP_ENV: production
      LAGO_DISABLE_SIGNUP: "true"

  lago-pdf:
    <<: *restart
    image: getlago/lago-gotenberg:7.8.2

  backend:
    <<: *restart
    image: ${ECR_REGISTRY}/{{ product_slug }}-backend:${BACKEND_TAG}
    env_file: [{path: .bootstrap/ids.env, required: false}]
    environment:
      DATABASE_URL: postgresql+psycopg://app:${APP_DB_PASSWORD}@${DB_HOST}:5432/app?sslmode=require
      FRONTEND_URL: https://app.${DOMAIN}
      ZITADEL_ISSUER: https://auth.${DOMAIN}
      ZITADEL_API_URL: https://auth.${DOMAIN}
      ZITADEL_SERVICE_TOKEN_FILE: /run/bootstrap/backend.pat
      LAGO_API_URL: http://lago-api:3000
      LAGO_API_KEY: ${LAGO_API_KEY}
      LAGO_WEBHOOK_ISSUER: https://lago-api.${DOMAIN}
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY:-}
    volumes: [./.bootstrap/backend:/run/bootstrap:ro]
    ports: ["127.0.0.1:8000:8000"]

  jobs:
    <<: *restart
    image: ${ECR_REGISTRY}/{{ product_slug }}-jobs:${JOBS_TAG}
    environment:
      DATABASE_URL: postgresql+psycopg://app:${APP_DB_PASSWORD}@${DB_HOST}:5432/app?sslmode=require
      LAGO_API_URL: http://lago-api:3000
      LAGO_API_KEY: ${LAGO_API_KEY}
      AWS_DEFAULT_REGION: ${AWS_REGION}
      RAW_BUCKET: ${DATA_BUCKET}

volumes: {caddy-data: {}}
```

`template/deploy/Caddyfile`:

```
{
	email {$ACME_EMAIL}
	{$CADDY_GLOBAL_OPTIONS}
}

auth.{$DOMAIN} {
	handle /ui/v2/login* {
		reverse_proxy zitadel-login:3000
	}
	handle {
		reverse_proxy h2c://zitadel-api:8080
	}
}

api.{$DOMAIN} {
	reverse_proxy backend:8000
}

# Stripe must reach the webhooks. Everything else in Lago is for people on the admin list.
lago-api.{$DOMAIN} {
	@webhooks path /webhooks/*
	handle @webhooks {
		reverse_proxy lago-api:3000
	}
	@admin remote_ip {$ADMIN_CIDRS}
	handle @admin {
		reverse_proxy lago-api:3000
	}
	handle {
		respond 403
	}
}

lago.{$DOMAIN} {
	@admin remote_ip {$ADMIN_CIDRS}
	handle @admin {
		reverse_proxy lago-front:80
	}
	handle {
		respond 403
	}
}
```

`template/deploy/db-init.sql`, run by `first-run.sh` with `psql -v` variables. Every statement is safe to re-run:

```sql
-- Run once as the RDS admin (database `postgres`). Zitadel creates its own role and database.
SELECT format('CREATE ROLE app LOGIN PASSWORD %L', :'app_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app') \gexec
SELECT format('CREATE ROLE lago LOGIN PASSWORD %L', :'lago_password')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lago') \gexec
GRANT app TO CURRENT_USER;
GRANT lago TO CURRENT_USER;
SELECT 'CREATE DATABASE app OWNER app' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'app') \gexec
SELECT 'CREATE DATABASE lago OWNER lago' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'lago') \gexec

-- Lago's migrations skip partitioning silently without this, and creating it needs rds_superuser.
\connect lago
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
GRANT ALL ON SCHEMA partman TO lago;
GRANT ALL ON ALL TABLES IN SCHEMA partman TO lago;
GRANT ALL ON ALL SEQUENCES IN SCHEMA partman TO lago;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA partman TO lago;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA partman TO lago;
```

- [ ] **Step 4: Run tests.** `uv run pytest tests/test_infra_template.py -q`. Expected: PASS. The local stack's behaviour is tested in Task 11.

- [ ] **Step 5: Commit.**

```bash
git add template/docker-compose.aws.yml.jinja template/deploy tests/test_infra_template.py
git commit -m "feat(infra): AWS Compose file, Caddy routing and database setup"
```

---

### Task 7: Server scripts: start, first run and deploy

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `first-run.sh` as written would fail: `bootstrap.py` reads `DOMAIN`, `SLUG`, `LAGO_API_KEY`, `LAGO_ORG_USER_EMAIL` and `LAGO_ORG_USER_PASSWORD` from its process environment, and nothing puts them there. Before `uv run`, export `DEPLOY_TARGET=aws`, `SLUG`, `DOMAIN`, `LAGO_API_KEY`, `LAGO_ORG_USER_PASSWORD`, `STRIPE_SECRET_KEY` from `val`, and `LAGO_ORG_USER_EMAIL=admin@$DOMAIN`, which matches the Compose file. Keep `val` tolerant of a missing key under `set -e`: `STRIPE_SECRET_KEY` usually isn't in `.env`. Add a test with stubs, including a `uv` stub that records its environment, that proves these reach it and that no value is printed.
- SSM Run Command gives no reliable `HOME` or `PATH`. All three scripts start with `export HOME="${HOME:-/root}"` and `PATH="$PATH:/usr/local/bin"`. Append to `PATH`, so test stubs still win.
- `template/scripts/tests/test_deploy_scripts.py` must pass `make check`'s `ruff check .`: tests don't have an S607 exemption, so add `# noqa: S607` where `bash` is called.
- Commit the three scripts with the executable bit.
- Fix round 1 (review): `deploy.sh` checks `up -d` (a failed start goes to rollback; a failed rollback restart prints "the service may be down"), retries `put-parameter` 3 times then exits 1 "deployed but not recorded", refuses with exit 1 when the previous tag is empty, needs 5 consecutive running polls for `jobs`, takes `flock -w 600` on `$APP_DIR/.deploy.lock` when `flock` exists (the sync in `user_data.sh.tftpl` excludes it), and exits 1 if `/etc/app.env` cannot be sourced. `start.sh` reads secrets and tags into variables before writing `.env`, treats only `ResourceNotFoundException` on the bootstrap secret as "no tokens yet" (other errors and non-JSON content exit non-zero), and uses `jq -er` per token. `first-run.sh` uses `jq -er .password` and splits `export` from assignment (SC2155).

**Files:**
- Create: `template/deploy/start.sh`, `template/deploy/first-run.sh`, `template/deploy/deploy.sh`, `template/scripts/tests/test_deploy_scripts.py`

**Interfaces:**
- Consumes: `/etc/app.env` from Task 4 (`SLUG`, `AWS_REGION`, `DEPLOY_BUCKET`), SSM `/<slug>/config`, `/<slug>/tags/backend`, `/<slug>/tags/jobs`, secrets `<slug>/app` and `<slug>/bootstrap`.
- Produces: `deploy.sh <backend|jobs> <tag>`, which exits 0 on success and 1 after rolling back. `APP_DIR` and `APP_ENV_FILE` environment overrides, for tests. The bootstrap secret holds JSON with keys `admin_pat`, `login_client_pat`, `backend_pat`, `ids_env`.

- [ ] **Step 1: Write the failing test.** `template/scripts/tests/test_deploy_scripts.py`. It runs the real scripts with stub `aws`, `docker` and `curl` commands on `PATH`:

```python
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
    return subprocess.run(["bash", str(DEPLOY / "deploy.sh"), *args], env=box["env"],  # type: ignore[arg-type]
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
    return subprocess.run(["bash", str(DEPLOY / "start.sh")], env=box["env"],  # type: ignore[arg-type]
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
```

- [ ] **Step 2: Run it to see it fail.** `make dev && cd .dev/acme/scripts && uv run pytest tests/test_deploy_scripts.py -q`. Expected: FAIL, scripts not found.

- [ ] **Step 3: Implement.**

`template/deploy/start.sh`:

```bash
#!/bin/bash
# Runs at boot and from first-run.sh. Renders .env from AWS, restores Zitadel's tokens, and starts
# the stack if first-run.sh has already happened. Safe to run again.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
source "${APP_ENV_FILE:-/etc/app.env}"
export AWS_REGION
cd "$APP_DIR"

secret() { aws secretsmanager get-secret-value --secret-id "$1" --query SecretString --output text; }
param() { aws ssm get-parameter --name "$1" --query Parameter.Value --output text; }
as_env() { jq -r 'to_entries[] | "\(.key)=\(.value)"'; }

umask 077
{
  secret "$SLUG/app" | as_env
  param "/$SLUG/config" | as_env
  echo "BACKEND_TAG=$(param "/$SLUG/tags/backend")"
  echo "JOBS_TAG=$(param "/$SLUG/tags/jobs")"
  echo "DEPLOY_TARGET=aws"
} > .env.new
mv .env.new .env
chmod 600 .env
umask 022

mkdir -p .bootstrap/zitadel .bootstrap/backend
tokens="$(secret "$SLUG/bootstrap" 2>/dev/null || echo '{}')"
if [ "$(echo "$tokens" | jq -r '.admin_pat // empty')" != "" ]; then
  echo "$tokens" | jq -r .admin_pat > .bootstrap/zitadel/admin.pat
  echo "$tokens" | jq -r .login_client_pat > .bootstrap/zitadel/login-client.pat
  echo "$tokens" | jq -r .backend_pat > .bootstrap/backend/backend.pat
  echo "$tokens" | jq -r .ids_env > .bootstrap/ids.env
  bootstrapped=1
else
  bootstrapped=0
fi
chown -R 1000:1000 .bootstrap 2>/dev/null || true

registry="$(grep '^ECR_REGISTRY=' .env | cut -d= -f2)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"

export COMPOSE_FILE=docker-compose.aws.yml
if [ "$bootstrapped" = 1 ]; then
  docker compose pull --quiet
  docker compose up -d
else
  echo "start: no saved tokens yet, so the stack waits for make infra-bootstrap"
fi
```

`template/deploy/first-run.sh`:

```bash
#!/bin/bash
# `make infra-bootstrap` runs this on the server. Safe to run again: each step looks before it creates.
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
source "${APP_ENV_FILE:-/etc/app.env}"
export AWS_REGION COMPOSE_FILE=docker-compose.aws.yml
cd "$APP_DIR"

"$APP_DIR/deploy/start.sh"

val() { grep "^$1=" .env | cut -d= -f2-; }
DB_ADMIN_PASSWORD="$(aws secretsmanager get-secret-value --secret-id "$(val DB_ADMIN_SECRET_ARN)" \
  --query SecretString --output text | jq -r .password)"
export DB_ADMIN_PASSWORD

echo "== databases"
docker run --rm -i -e PGPASSWORD="$DB_ADMIN_PASSWORD" -e PGSSLMODE=require postgres:15-alpine \
  psql -v ON_ERROR_STOP=1 -h "$(val DB_HOST)" -U dbadmin -d postgres \
  -v app_password="$(val APP_DB_PASSWORD)" -v lago_password="$(val LAGO_DB_PASSWORD)" < deploy/db-init.sql

echo "== Zitadel's database"
docker compose --profile setup run --rm zitadel-init
unset DB_ADMIN_PASSWORD

echo "== stack"
docker compose pull --quiet
docker compose up -d

echo "== bootstrap"
cd scripts
uv run python -u bootstrap.py

echo "== restart with the saved ids and tokens"
cd "$APP_DIR"
docker compose up -d --force-recreate backend jobs
```

`template/deploy/deploy.sh`:

```bash
#!/bin/bash
# deploy.sh <backend|jobs> <tag>. Run by CI through SSM. Exit 2 refused, 1 failed and rolled back.
set -uo pipefail
APP_DIR="${APP_DIR:-/opt/app}"
service="${1:-}"
tag="${2:-}"

case "$service" in
  backend) tag_key=BACKEND_TAG ;;
  jobs) tag_key=JOBS_TAG ;;
  *) echo "deploy: unknown service '$service'" >&2; exit 2 ;;
esac
if ! [[ "$tag" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "deploy: '$tag' is not a commit tag" >&2
  exit 2
fi

source "${APP_ENV_FILE:-/etc/app.env}"
export AWS_REGION COMPOSE_FILE=docker-compose.aws.yml
cd "$APP_DIR" || exit 1

set_tag() { sed -i.bak "s/^$tag_key=.*/$tag_key=$1/" .env && rm -f .env.bak; }
previous="$(grep "^$tag_key=" .env | cut -d= -f2)"

registry="$(grep '^ECR_REGISTRY=' .env | cut -d= -f2)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry" || exit 1

set_tag "$tag"
if ! docker compose pull --quiet "$service"; then
  echo "deploy: could not pull $service:$tag" >&2
  set_tag "$previous"
  exit 1
fi

if [ "$service" = backend ]; then
  if ! docker compose run --rm --no-deps backend uv run --no-dev alembic upgrade head; then
    echo "deploy: migration failed, the previous version keeps running" >&2
    set_tag "$previous"
    exit 1
  fi
fi

docker compose up -d "$service"

healthy() {
  if [ "$service" = backend ]; then
    curl -fsS -m 5 http://127.0.0.1:8000/health > /dev/null
  else
    docker compose ps --status running --services | grep -qx jobs
  fi
}

for _ in $(seq 1 30); do
  if healthy; then
    aws ssm put-parameter --name "/$SLUG/tags/$service" --value "$tag" --type String --overwrite > /dev/null
    echo "deploy: $service is on $tag"
    exit 0
  fi
  sleep 2
done

echo "deploy: $service:$tag failed its health check, going back to $previous" >&2
set_tag "$previous"
docker compose up -d "$service"
exit 1
```

`ADMIN_CIDRS` can hold spaces, which Compose's `.env` parser accepts but `source` doesn't. So `first-run.sh` reads single values with `val`, and never sources `.env`.

- [ ] **Step 4: Run tests.** `cd .dev/acme/scripts && uv run pytest tests/test_deploy_scripts.py -q` after `make dev`. Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add template/deploy template/scripts/tests/test_deploy_scripts.py
git commit -m "feat(infra): server start, first-run and deploy scripts with rollback"
```

---

### Task 8: Bootstrap on AWS

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `main`: on AWS `stripe_webhook_secret` must not run, because it calls the `stripe-cli` service, which isn't in the AWS file: `webhook_secret = stripe_webhook_secret() if key and not on_aws() else ""`.
- `bootstrap_stripe`: when `on_aws()`, skip both `compose("up", ..., "stripe-cli")` and `apply_stripe_webhook_secret`, and print a line saying Lago registers its own webhook. Lago's `RegisterWebhookJob` does this because `LAGO_API_URL` is public.
- `main`: the final `wait_for(the app ...)` is local-only too, along with recreating `frontend`. On AWS the frontend isn't deployed yet.
- Call `publish_aws_state()` straight after `bootstrap_lago()` and before `ensure_bucket()` and the brand step, because brand needs Lago's S3 and that's the likeliest thing to fail on a first deploy. Tokens must already be saved by then.
- `brand.py` `main`: the server's bundle has no `frontend/`, so `write_frontend` and its print are skipped when `DEPLOY_TARGET=aws`. Add a test.
- `pyproject.toml`: add `aws_state.py` to mypy's `files`, and a `[[tool.mypy.overrides]]` for `boto3` with `ignore_missing_imports = true`.
- Implemented as amended; deviations: `test_aws_state.py` uses `match=r"backend\.pat"` (ruff RUF043), and `test_bootstrap.py` adds tests that `bootstrap_stripe` and `ensure_bucket` do nothing local on AWS. The Ready summary builds the S3 line only locally.
- Review fix round 1: `publish_aws_state` saves tokens before the SSM parameter and turns `BotoCoreError`/`ClientError` into a `bootstrap:` stop naming class and code only; on AWS the Ready summary points to `gh workflow run deploy-frontend` instead of "Open"; mypy override covers `botocore.*` too; tests added for AWS `main()` and `publish_aws_state`.

**Files:**
- Create: `template/scripts/aws_state.py`, `template/scripts/tests/test_aws_state.py`
- Modify: `template/scripts/bootstrap.py`, `template/scripts/tests/test_bootstrap.py`, `template/scripts/pyproject.toml`, `template/scripts/uv.lock`

**Interfaces:**
- Consumes: `DEPLOY_TARGET=aws`, `DOMAIN`, `SLUG`, `AWS_REGION` from `.env` (Task 7). Token and ID files under `.bootstrap/`.
- Produces: SSM `/<slug>/frontend` with JSON `{"VITE_API_BASE_URL", "ZITADEL_ISSUER", "ZITADEL_CLIENT_ID", "ZITADEL_PROJECT_ID"}`, which Task 10 reads. `aws_state.frontend_values(domain, client_id, project_id) -> dict[str, str]`, `aws_state.publish_frontend(ssm, slug, values) -> None`, `aws_state.save_tokens(secrets, slug, state_dir) -> None`.

- [ ] **Step 1: Write the failing tests.**

`template/scripts/tests/test_aws_state.py`:

```python
import json
import pathlib
from unittest.mock import MagicMock

import pytest

import aws_state


def test_frontend_values_are_public_https_urls_and_ids() -> None:
    assert aws_state.frontend_values("x.test", "c1", "p1") == {
        "VITE_API_BASE_URL": "https://api.x.test",
        "ZITADEL_ISSUER": "https://auth.x.test",
        "ZITADEL_CLIENT_ID": "c1",
        "ZITADEL_PROJECT_ID": "p1",
    }


def test_publish_frontend_writes_the_parameter() -> None:
    ssm = MagicMock()
    aws_state.publish_frontend(ssm, "acme", {"A": "1"})
    ssm.put_parameter.assert_called_once_with(
        Name="/acme/frontend", Value=json.dumps({"A": "1"}), Type="String", Overwrite=True)


def state_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "zitadel").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "zitadel/admin.pat").write_text("A\n")
    (tmp_path / "zitadel/login-client.pat").write_text("L\n")
    (tmp_path / "backend/backend.pat").write_text("B\n")
    (tmp_path / "ids.env").write_text("X=1\n")
    return tmp_path


def test_save_tokens_stores_all_four(tmp_path: pathlib.Path) -> None:
    secrets = MagicMock()
    aws_state.save_tokens(secrets, "acme", state_dir(tmp_path))
    call = secrets.put_secret_value.call_args.kwargs
    assert call["SecretId"] == "acme/bootstrap"
    assert json.loads(call["SecretString"]) == {
        "admin_pat": "A", "login_client_pat": "L", "backend_pat": "B", "ids_env": "X=1\n"}


def test_save_tokens_refuses_a_partial_set(tmp_path: pathlib.Path) -> None:
    root = state_dir(tmp_path)
    (root / "backend/backend.pat").unlink()
    secrets = MagicMock()
    with pytest.raises(SystemExit, match="backend.pat"):
        aws_state.save_tokens(secrets, "acme", root)
    secrets.put_secret_value.assert_not_called()
```

Add to `template/scripts/tests/test_bootstrap.py`, importing `bootstrap` as that file already does:

```python
def test_aws_urls_are_https_without_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    assert bootstrap.zitadel_url() == "https://auth.x.test"
    assert bootstrap.app_url() == "https://app.x.test"
    assert bootstrap.public_url("api", "API_PORT") == "https://api.x.test"


def test_on_aws_zitadel_is_reached_publicly_and_lago_on_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    assert bootstrap.local("https://auth.x.test") == ("https://auth.x.test", {})
    assert bootstrap.local("https://lago-api.x.test") == (
        "http://127.0.0.1:3000", {"Host": "lago-api.x.test", "X-Forwarded-Proto": "https"})


def test_on_aws_redirects_must_be_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    assert bootstrap.web_app_config("https://app.x.test")["devMode"] is False


def test_locally_nothing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEPLOY_TARGET", raising=False)
    monkeypatch.setenv("ZITADEL_PORT", "8085")
    assert bootstrap.zitadel_url().startswith("http://auth.")
    assert bootstrap.web_app_config("http://x.localhost:5173")["devMode"] is True
```

- [ ] **Step 2: Run them to see them fail.** `make dev && cd .dev/acme/scripts && uv run pytest tests/test_aws_state.py tests/test_bootstrap.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/scripts/aws_state.py`:

```python
"""Bootstrap's AWS side: the values the frontend build needs, and saving Zitadel's tokens.

Zitadel writes its tokens only on its first start against an empty database, so a replaced server
gets them back from Secrets Manager (deploy/start.sh). Passed boto3 clients, so tests need no AWS.
"""

import json
from pathlib import Path
from typing import Any


def frontend_values(domain: str, client_id: str, project_id: str) -> dict[str, str]:
    return {
        "VITE_API_BASE_URL": f"https://api.{domain}",
        "ZITADEL_ISSUER": f"https://auth.{domain}",
        "ZITADEL_CLIENT_ID": client_id,
        "ZITADEL_PROJECT_ID": project_id,
    }


def publish_frontend(ssm: Any, slug: str, values: dict[str, str]) -> None:
    ssm.put_parameter(Name=f"/{slug}/frontend", Value=json.dumps(values), Type="String", Overwrite=True)


def save_tokens(secrets: Any, slug: str, state_dir: Path) -> None:
    files = {
        "admin_pat": state_dir / "zitadel" / "admin.pat",
        "login_client_pat": state_dir / "zitadel" / "login-client.pat",
        "backend_pat": state_dir / "backend" / "backend.pat",
        "ids_env": state_dir / "ids.env",
    }
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise SystemExit(f"bootstrap: can't save tokens, missing {', '.join(missing)}")
    values = {k: (p.read_text() if k == "ids_env" else p.read_text().strip()) for k, p in files.items()}
    secrets.put_secret_value(SecretId=f"{slug}/bootstrap", SecretString=json.dumps(values))
```

In `template/scripts/pyproject.toml`, add `"boto3>=1.40"` to `dependencies`. Run `uv lock` in `template/scripts`.

In `template/scripts/bootstrap.py`, by function:

```python
def on_aws() -> bool:
    return os.environ.get("DEPLOY_TARGET") == "aws"


def public_url(sub: str, port_var: str) -> str:
    if on_aws():
        return f"https://{sub}.{env('DOMAIN')}"
    host = f"{sub}.{product.DOMAIN}" if sub else product.DOMAIN
    return f"http://{host}:{env(port_var)}"


def app_url() -> str:
    return public_url("app", "APP_PORT") if on_aws() else public_url("", "APP_PORT")


def local(url: str) -> tuple[str, dict[str, str]]:
    """Where this process reaches a public URL.

    Locally: 127.0.0.1 plus the Host header the service routes on (Zitadel picks its instance by Host,
    and not every resolver maps *.localhost to 127.0.0.1). On AWS: Zitadel through its public URL, and
    Lago on loopback, because Caddy keeps its public API closed.
    """
    parts = urlsplit(url)
    if on_aws():
        if parts.netloc.startswith("lago-api."):
            return "http://127.0.0.1:3000", {"Host": parts.netloc, "X-Forwarded-Proto": "https"}
        return url, {}
    return f"http://127.0.0.1:{parts.port}", {"Host": parts.netloc}
```

Also:

- In `web_app_config`, change `"devMode": True,  # allows http:// redirect URIs` to `"devMode": not on_aws(),  # local redirect URIs are http://`.
- In `ensure_bucket`, add as its first line: `if on_aws(): return  # Terraform creates the bucket`.
- In `compose`, nothing changes: `COMPOSE_FILE` from `first-run.sh` selects the file.
- In `main`, make these changes. `first-run.sh` recreates backend and jobs after this returns, and tokens are saved before the steps that can fail later:

```python
    bootstrap_zitadel()
    bootstrap_lago()
    ensure_bucket()
    # ... existing brand step ...
    if on_aws():
        publish_aws_state()
    compose("up", "-d", "--force-recreate", "backend")
```

and wrap the final local-only steps:

```python
    if not on_aws():
        compose("up", "-d", "--force-recreate", "frontend")
```

Skip whatever step recreates `stripe-cli` in `bootstrap_stripe` when `on_aws()`; on AWS, Stripe calls Lago's public webhook URL, and the local listener's secret step doesn't apply. On AWS, `bootstrap_stripe` registers the webhook endpoint using Lago's own registration instead of `apply_stripe_webhook_secret`, which stays local only. The real Stripe run isn't part of this milestone, so if no key is set, this path stays dormant.

Add:

```python
def publish_aws_state() -> None:
    import boto3

    import aws_state

    ids = read_ids()
    region, slug = env("AWS_REGION"), env("SLUG")
    aws_state.publish_frontend(
        boto3.client("ssm", region_name=region), slug,
        aws_state.frontend_values(env("DOMAIN"), ids["ZITADEL_CLIENT_ID"], ids["ZITADEL_PROJECT_ID"]))
    aws_state.save_tokens(boto3.client("secretsmanager", region_name=region), slug, STATE)
```

Also change the final printed summary so that on AWS it omits the local S3 line.

- [ ] **Step 4: Run tests.** `make dev && cd .dev/acme/scripts && uv run ruff check . && uv run mypy && uv run pytest -q`. Expected: all PASS, including every existing bootstrap test.

- [ ] **Step 5: Commit.**

```bash
git add template/scripts
git commit -m "feat(infra): bootstrap runs on AWS and saves tokens and frontend values"
```

---

### Task 9: The `make infra-*` commands

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- `pyproject.toml`: add `infra.py` and `infra_doctor.py` to mypy's `files`. Fix what strict mode reports, for example `json.loads` returning `Any` from `read_secret`.
- `infra_doctor.main`: `admin_set` must not depend on spacing. Use `not re.search(r"^\s*admin_cidrs\s*=\s*\[\s*\]", text, re.M)`.
- `destroy`: drop `-auto-approve` from both Terraform steps. Spec §6 says the protection change is a separate, visible plan, so a person reads and confirms each one.
- `destroy` also deletes this product's SSM parameters that Terraform doesn't own (`/<slug>/tags/*`, `/<slug>/frontend`), through a small `delete_parameters(ssm, slug)` with a MagicMock-based test. Otherwise a redeploy of the slug starts from stale tags, and "removes everything" is false.
- `upload_bundle` also skips `.pytest_cache`, `.mypy_cache` and `.ruff_cache`.
- `infra-plan` first prints the account (spec §6): `@echo "Account: $$(aws sts get-caller-identity --query Account --output text)"`.
- Implementation notes (Task 9 run): `read_secret` and `run_on_server` wrap their `Any` results (`value: dict[str, str]`, `str(...)`) for strict mypy; `# noqa: S603, S607` on Terraform/docker calls; `rehearse-aws` was dropped from the new `.PHONY` line because no such target exists yet; `delete_parameters` uses the fixed names `/<slug>/tags/{backend,jobs}` and `/<slug>/frontend`.

**Files:**
- Create: `template/scripts/infra.py`, `template/scripts/infra_doctor.py`, `template/scripts/tests/test_infra.py`, `template/scripts/tests/test_infra_doctor.py`
- Modify: `template/Makefile`

**Interfaces:**
- Consumes: `infra/terraform.tfvars`, Terraform outputs `server_instance_id`, `server_ip`, `deploy_role_arn`, `make_env.generate(command) -> str`.
- Produces: `infra.read_tfvars(path) -> dict[str, str]`, `infra.check_account(actual, expected) -> None`, `infra.fill_secrets(existing, generate) -> dict[str, str]`, `infra.smtp_password(secret_key, region) -> str`, `infra.check_stripe_key(key) -> str`, `infra_doctor.problems(results) -> list[str]`, and the make targets.

- [ ] **Step 1: Write the failing tests.**

`template/scripts/tests/test_infra.py`:

```python
import base64
import pathlib

import pytest

import infra


def test_read_tfvars(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "terraform.tfvars"
    path.write_text('# note\nslug = "acme"\naws_account_id   = "123"\nadmin_cidrs = []\n')
    assert infra.read_tfvars(path) == {"slug": "acme", "aws_account_id": "123"}


def test_wrong_account_is_refused() -> None:
    infra.check_account("123", "123")
    with pytest.raises(SystemExit, match="999.*123"):
        infra.check_account("999", "123")


def test_placeholder_account_is_refused() -> None:
    with pytest.raises(SystemExit, match="terraform.tfvars"):
        infra.check_account("000000000000", "000000000000")


def test_filling_secrets_never_changes_an_existing_value() -> None:
    existing = {"ZITADEL_MASTERKEY": "keep-me", "LAGO_API_KEY": "keep-too"}
    filled = infra.fill_secrets(existing, lambda command: f"new:{command}")
    assert filled["ZITADEL_MASTERKEY"] == "keep-me"
    assert filled["LAGO_API_KEY"] == "keep-too"
    assert filled["SECRET_KEY_BASE"] == "new:openssl rand -hex 64"
    assert set(infra.SECRET_SPECS) <= set(filled)


def test_filling_twice_changes_nothing() -> None:
    once = infra.fill_secrets({}, lambda command: "x")
    assert infra.fill_secrets(once, lambda command: "y") == once


def test_smtp_password_has_the_documented_shape() -> None:
    password = infra.smtp_password("secret", "us-west-2")
    raw = base64.b64decode(password)
    assert raw[0] == 4 and len(raw) == 33
    assert password != infra.smtp_password("secret", "us-east-1")


@pytest.mark.parametrize("key", ["sk_live_abc", "rk_test_abc", "", "whatever"])
def test_only_stripe_test_keys_are_accepted(key: str) -> None:
    with pytest.raises(SystemExit):
        infra.check_stripe_key(key)


def test_stripe_test_key_is_accepted() -> None:
    assert infra.check_stripe_key(" sk_test_abc\n") == "sk_test_abc"
```

`template/scripts/tests/test_infra_doctor.py`:

```python
import infra_doctor


def good() -> dict[str, object]:
    return {
        "dns": {"auth.x.test": "1.2.3.4", "api.x.test": "1.2.3.4"},
        "server_ip": "1.2.3.4",
        "http": {"https://auth.x.test/debug/ready": 200, "https://api.x.test/health": 200,
                 "https://app.x.test/": 200, "https://lago-api.x.test/api/v1/plans": 403,
                 "https://lago.x.test/": 403},
        "partman": "1",
    }


def test_healthy_product_has_no_problems() -> None:
    assert infra_doctor.problems(good()) == []


def test_dns_pointing_elsewhere_is_named() -> None:
    results = good()
    results["dns"] = {"auth.x.test": "9.9.9.9", "api.x.test": "1.2.3.4"}
    assert any("auth.x.test" in p and "9.9.9.9" in p for p in infra_doctor.problems(results))


def test_certificate_failure_points_at_dns() -> None:
    results = good()
    results["http"]["https://api.x.test/health"] = 0  # type: ignore[index]
    assert any("api.x.test" in p and "DNS" in p for p in infra_doctor.problems(results))


def test_missing_partman_is_a_problem() -> None:
    results = good()
    results["partman"] = "0"
    assert any("pg_partman" in p for p in infra_doctor.problems(results))


def test_lago_being_public_is_a_problem() -> None:
    results = good()
    results["http"]["https://lago-api.x.test/api/v1/plans"] = 200  # type: ignore[index]
    assert any("lago-api" in p and "public" in p for p in infra_doctor.problems(results))
```

An admin whose own IP is on `admin_cidrs` will see 401 instead of 403 from Lago's API, and 200 from its UI. `infra_doctor` treats those as "public" only when `admin_cidrs` is empty, by passing `results["admin_cidrs_set"]`. Add that key with default `False`, and a test that a `200` on `lago.x.test` is allowed when it's `True`.

- [ ] **Step 2: Run them to see them fail.** `make dev && cd .dev/acme/scripts && uv run pytest tests/test_infra.py tests/test_infra_doctor.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/scripts/infra.py`:

```python
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
    made = boto3.Session(region_name=tfvars["aws_region"])
    check_account(made.client("sts").get_caller_identity()["Account"], tfvars["aws_account_id"])
    return made


def state_bucket(tfvars: dict[str, str]) -> str:
    return f"{tfvars['slug']}-tfstate-{tfvars['aws_account_id']}"


def terraform_output(name: str) -> str:
    return subprocess.run(["terraform", "output", "-raw", name], cwd=INFRA, check=True,  # noqa: S607
                          capture_output=True, text=True).stdout.strip()


def init() -> None:
    tfvars, aws = read_tfvars(), session()
    s3, bucket, region = aws.client("s3"), state_bucket(read_tfvars()), tfvars["aws_region"]
    if bucket not in [b["Name"] for b in s3.list_buckets()["Buckets"]]:
        config = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
        s3.create_bucket(Bucket=bucket, **config)
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    (INFRA / "backend.hcl").write_text(
        f'bucket = "{bucket}"\nkey = "terraform.tfstate"\nregion = "{region}"\nencrypt = true\nuse_lockfile = true\n')
    subprocess.run(["terraform", "init", "-backend-config=backend.hcl", "-input=false"], cwd=INFRA, check=True)  # noqa: S607


def read_secret(secrets: Any, secret_id: str) -> dict[str, str]:
    try:
        return json.loads(secrets.get_secret_value(SecretId=secret_id)["SecretString"])
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


def release() -> None:
    tfvars, aws = read_tfvars(), session()
    slug, region, account, tag = tfvars["slug"], tfvars["aws_region"], tfvars["aws_account_id"], git_commit()
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com"
    token = base64.b64decode(aws.client("ecr").get_authorization_token()["authorizationData"][0]["authorizationToken"]).decode().split(":", 1)[1]
    subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin", registry],  # noqa: S607
                   input=token, text=True, check=True, capture_output=True)
    ssm = aws.client("ssm")
    for service in ["backend", "jobs"]:
        image = f"{registry}/{slug}-{service}:{tag}"
        subprocess.run(["docker", "build", "--platform", "linux/amd64", "-t", image, service], cwd=ROOT, check=True)  # noqa: S607
        subprocess.run(["docker", "push", image], check=True)  # noqa: S607
        ssm.put_parameter(Name=f"/{slug}/tags/{service}", Value=tag, Type="String", Overwrite=True)
    upload_bundle(aws.client("s3"), f"{slug}-deploy-{account}")
    print(f"Released {tag}.")


BUNDLE = ["docker-compose.aws.yml", "deploy", "scripts", "brand"]


def upload_bundle(s3: Any, bucket: str) -> None:
    """Deploy files as plain objects under current/, for `aws s3 sync` on the server."""
    for name in BUNDLE:
        path = ROOT / name
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()
                                               and ".venv" not in p.parts and "__pycache__" not in p.parts]
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
            return result["StandardOutputContent"]
    raise SystemExit("on the server: gave up waiting")


def bootstrap() -> None:
    aws = session()
    run_on_server(aws, terraform_output("server_instance_id"), "app-start || true; /opt/app/deploy/first-run.sh")


def destroy() -> None:
    tfvars, aws = read_tfvars(), session()
    slug = tfvars["slug"]
    print(f"This deletes {slug}, its database and its backups, in account {tfvars['aws_account_id']}.")
    if input(f"Type {slug} to continue: ") != slug:
        raise SystemExit("Not deleted.")
    for step in (["apply", "-auto-approve", "-var", "protect=false"], ["destroy", "-auto-approve", "-var", "protect=false"]):
        subprocess.run(["terraform", *step], cwd=INFRA, check=True)  # noqa: S607
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
```

`plans.yaml` isn't bundled because it's inside the backend image (`backend/app/billing/`).

`template/scripts/infra_doctor.py`:

```python
"""`make infra-doctor`: checks a deployed product from outside, then from the server. Exit 1 on any problem."""

import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

PARTMAN_CHECK = (
    "cd /opt/app && COMPOSE_FILE=docker-compose.aws.yml docker compose exec -T lago-api bin/rails runner "
    "\"puts ActiveRecord::Base.connection.select_value(\\\"select count(*) from pg_extension where extname='pg_partman'\\\")\""
)


def problems(results: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for host, ip in results["dns"].items():
        if ip != results["server_ip"]:
            found.append(f"DNS: {host} points at {ip}, not the server at {results['server_ip']}")
    admin_set = results.get("admin_cidrs_set", False)
    for url, status in results["http"].items():
        host = urlsplit(url).netloc
        if host.startswith("lago"):
            if status != 403 and not admin_set:
                found.append(f"{host} looks public (HTTP {status}); only its webhooks should be")
        elif status == 0:
            found.append(f"{host}: no HTTPS answer. Usually the certificate isn't issued yet because DNS isn't pointing at the server")
        elif status != 200:
            found.append(f"{url} answered HTTP {status}")
    if results["partman"] != "1":
        found.append("pg_partman isn't installed in Lago's database, and Lago skips its setup silently. Re-run make infra-bootstrap")
    return found


def status_of(url: str) -> int:
    try:
        return httpx.get(url, timeout=15.0, follow_redirects=True).status_code
    except httpx.HTTPError:
        return 0


def resolve(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "nothing"


def main() -> None:
    import infra

    tfvars, aws = infra.read_tfvars(), infra.session()
    domain, server_ip = tfvars["domain"], infra.terraform_output("server_ip")
    admin_set = "admin_cidrs" in (infra.TFVARS.read_text()) and "admin_cidrs        = []" not in infra.TFVARS.read_text()
    output = infra.run_on_server(aws, infra.terraform_output("server_instance_id"), PARTMAN_CHECK, timeout_s=120)
    results = {
        "dns": {h: resolve(h) for h in [f"{s}.{domain}" for s in ["auth", "api", "lago", "lago-api"]]},
        "server_ip": server_ip,
        "admin_cidrs_set": admin_set,
        "http": {u: status_of(u) for u in [
            f"https://auth.{domain}/debug/ready", f"https://api.{domain}/health", f"https://app.{domain}/",
            f"https://lago-api.{domain}/api/v1/plans", f"https://lago.{domain}/"]},
        "partman": output.strip().splitlines()[-1] if output.strip() else "0",
    }
    found = problems(results)
    for problem in found:
        print(f"PROBLEM: {problem}")
    if found:
        raise SystemExit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
```

`template/Makefile`: add to `.PHONY`, and add at the end. Secrets from a local `.env` must not reach these host processes, because they talk to AWS, not the local stack:

```make
# AWS. See infra/README.md. Set AWS_PROFILE first.
.PHONY: infra-init infra-plan infra-apply infra-secrets infra-set-stripe-key infra-release infra-bootstrap infra-doctor infra-destroy rehearse-aws

infra-init:
	cd scripts && uv run python infra.py init

infra-plan:
	cd infra && terraform plan -input=false -out=tfplan
	@echo "Check the plan for 'destroy' and 'replace' before running make infra-apply."

infra-apply:
	cd infra && terraform apply -input=false tfplan && rm -f tfplan
	@cd infra && echo "Set the GitHub variables: gh variable set AWS_DEPLOY_ROLE_ARN -b $$(terraform output -raw deploy_role_arn); gh variable set AWS_REGION -b $$(terraform output -raw aws_region)"

infra-secrets:
	cd scripts && uv run python infra.py secrets

infra-set-stripe-key:
	cd scripts && uv run python infra.py set-stripe-key

infra-release:
	cd scripts && uv run python infra.py release

infra-bootstrap:
	cd scripts && uv run python infra.py bootstrap

infra-doctor:
	cd scripts && uv run python infra_doctor.py

infra-destroy:
	cd scripts && uv run python infra.py destroy
```

Add the same fast check that the `make` targets exist to `tests/test_infra_template.py`:

```python
def test_make_has_every_infra_command(product_dir: pathlib.Path) -> None:
    makefile = (product_dir / "Makefile").read_text()
    for target in ["infra-init", "infra-plan", "infra-apply", "infra-secrets", "infra-set-stripe-key",
                   "infra-release", "infra-bootstrap", "infra-doctor", "infra-destroy"]:
        assert f"\n{target}:" in makefile, target
```

- [ ] **Step 4: Run tests.** `make dev && cd .dev/acme/scripts && uv run ruff check . && uv run mypy && uv run pytest -q`, then `uv run pytest tests/test_infra_template.py -q` at the repo root. Expected: PASS. Don't run any command that talks to AWS.

- [ ] **Step 5: Commit.**

```bash
git add template/scripts template/Makefile tests/test_infra_template.py
git commit -m "feat(infra): make infra-* commands and infra-doctor"
```

---

### Task 10: Deploy workflows

**Amendments, 2026-11-01:** `deploy-backend.yml` and `deploy-jobs.yml` both use `concurrency: {group: deploy-server}`, so one merge touching both folders doesn't run two deploys on one server at once (found in Task 7's review; `deploy.sh` also takes a lock).

**Files:**
- Create: `template/.github/workflows/deploy-frontend.yml`, `deploy-backend.yml`, `deploy-jobs.yml`
- Test: `tests/test_workflows.py`

**Interfaces:**
- Consumes: repo variables `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION` (`make infra-apply` prints the commands), SSM `/<slug>/config` and `/<slug>/frontend`, SSM document `<slug>-deploy`.
- Produces: per-folder deploys on merge to `main`, skipped when `AWS_DEPLOY_ROLE_ARN` isn't set, so a product not yet on AWS has green CI.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_workflows.py`:

```python
DEPLOYS = {"deploy-frontend.yml": "frontend/**", "deploy-backend.yml": "backend/**", "deploy-jobs.yml": "jobs/**"}


def test_each_folder_deploys_alone_from_main_only() -> None:
    for name, path in DEPLOYS.items():
        workflow = yaml.safe_load((ROOT / "template/.github/workflows" / name).read_text())
        on = workflow[True]  # YAML reads `on` as True
        assert on["push"]["branches"] == ["main"]
        assert path in on["push"]["paths"]
        for other in set(DEPLOYS.values()) - {path}:
            assert other not in on["push"]["paths"]
        assert workflow["permissions"]["id-token"] == "write"
        job = next(iter(workflow["jobs"].values()))
        assert job["if"] == "vars.AWS_DEPLOY_ROLE_ARN != ''"


def test_deploys_use_no_stored_aws_keys() -> None:
    for name in DEPLOYS:
        text = (ROOT / "template/.github/workflows" / name).read_text()
        assert "AWS_SECRET_ACCESS_KEY" not in text and "secrets." not in text
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_workflows.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement.**

`template/.github/workflows/deploy-frontend.yml`:

```yaml
name: deploy-frontend
on:
  push:
    branches: [main]
    paths: ["frontend/**", ".github/workflows/deploy-frontend.yml"]
  workflow_dispatch:
permissions: {contents: read, id-token: write}
concurrency: {group: deploy-frontend}
jobs:
  deploy:
    if: vars.AWS_DEPLOY_ROLE_ARN != ''
    runs-on: ubuntu-24.04
    defaults: {run: {working-directory: frontend}}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with: {node-version: "22.23.1", cache: npm, cache-dependency-path: frontend/package-lock.json}
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: Read the public build values
        run: |
          slug="$(basename "$AWS_ROLE" -deploy)"
          aws ssm get-parameter --name "/$slug/frontend" --query Parameter.Value --output text \
            | jq -r 'to_entries[] | "\(.key)=\(.value)"' >> "$GITHUB_ENV"
          config="$(aws ssm get-parameter --name "/$slug/config" --query Parameter.Value --output text)"
          echo "BUCKET=$(echo "$config" | jq -r .FRONTEND_BUCKET)" >> "$GITHUB_ENV"
          echo "DISTRIBUTION=$(echo "$config" | jq -r .DISTRIBUTION_ID)" >> "$GITHUB_ENV"
        env:
          AWS_ROLE: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
      - run: npm ci --no-audit --no-fund
      - run: npm run build
      - name: Upload. index.html last, so it never points at files that aren't there yet
        run: |
          aws s3 sync dist "s3://$BUCKET" --exclude index.html --cache-control "public,max-age=31536000,immutable"
          aws s3 cp dist/index.html "s3://$BUCKET/index.html" --cache-control "no-cache"
          aws s3 sync dist "s3://$BUCKET" --delete --exclude index.html
          aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION" --paths "/index.html"
```

`template/.github/workflows/deploy-backend.yml`:

```yaml
name: deploy-backend
on:
  push:
    branches: [main]
    paths: ["backend/**", ".github/workflows/deploy-backend.yml"]
  workflow_dispatch:
permissions: {contents: read, id-token: write}
concurrency: {group: deploy-server}
jobs:
  deploy:
    if: vars.AWS_DEPLOY_ROLE_ARN != ''
    runs-on: ubuntu-24.04
    env:
      SERVICE: backend
      AWS_ROLE: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: Build and push
        run: |
          slug="$(basename "$AWS_ROLE" -deploy)"
          tag="$(git rev-parse --short=12 HEAD)"
          registry="$(aws ssm get-parameter --name "/$slug/config" --query Parameter.Value --output text | jq -r .ECR_REGISTRY)"
          aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
          docker build -t "$registry/$slug-$SERVICE:$tag" "$SERVICE"
          docker push "$registry/$slug-$SERVICE:$tag"
          echo "SLUG=$slug" >> "$GITHUB_ENV"
          echo "TAG=$tag" >> "$GITHUB_ENV"
      - name: Deploy on the server
        run: |
          instance="$(aws ssm get-parameter --name "/$SLUG/config" --query Parameter.Value --output text | jq -r .INSTANCE_ID)"
          command_id="$(aws ssm send-command --instance-ids "$instance" --document-name "$SLUG-deploy" \
            --parameters "service=$SERVICE,tag=$TAG" --query Command.CommandId --output text)"
          sleep 5
          aws ssm wait command-executed --command-id "$command_id" --instance-id "$instance" || true
          aws ssm get-command-invocation --command-id "$command_id" --instance-id "$instance" \
            --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
          status="$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$instance" --query Status --output text)"
          test "$status" = Success
```

`template/.github/workflows/deploy-jobs.yml`: identical to `deploy-backend.yml`, with `name: deploy-jobs`, `paths: ["jobs/**", ".github/workflows/deploy-jobs.yml"]`, and `SERVICE: jobs`.

- [ ] **Step 4: Run tests.** `uv run pytest tests/test_workflows.py tests/test_infra_template.py -q`. Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add template/.github/workflows tests/test_workflows.py
git commit -m "feat(infra): per-folder deploy workflows over OIDC"
```

---

### Task 11: Local rehearsal, without AWS

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- Ports 80 and others are taken on developers' machines, and every check runs inside the Compose network. So the rehearsal publishes nothing: `ports: !reset []` on `caddy` and `lago-api` in the override file.
- The file is `deploy/rehearsal/rehearsal.env`, not `.env.rehearsal`. The guard (rightly) blocks `.env.*` names and `.gitignore` ignores them, so no `.gitignore` exception is needed for it.
- Project name: the slug from `docker-compose.aws.yml`'s `name:` plus `-rehearsal`, so two products don't clash.
- Never touch the product's `.bootstrap/`, which a local stack may be using. `run.sh` makes a `chmod 777` temp folder under a git-ignored `.rehearsal/` (add it to `template/.gitignore`), and the override file mounts it over Zitadel's and the login's bootstrap volumes using `!override`.
- Use the one-shot `curl` container with `--resolve name:443:<caddy ip>` and `-k` from the start, since Caddy picks certificates by SNI. Pin an exact `curlimages/curl` tag.
- For a useful memory figure, also start `zitadel-login`, `lago-worker`, `lago-clock` and `lago-front`, and print the total. The backend and jobs aren't running, because they have no image here; say so in the output.
- `db-init.sql` runs as the stand-in superuser because `pg_partman` isn't a trusted extension here, while on RDS `dbadmin` runs it as `rds_superuser`. That difference is a limit of this rehearsal, and the output should say so.

This is the only test of the database setup and routing before real money is spent. It stands in for RDS with a Postgres that requires TLS, and an admin that isn't a superuser.

**Files:**
- Create: `template/deploy/rehearsal/docker-compose.rehearsal.yml`, `template/deploy/rehearsal/run.sh`, `template/deploy/rehearsal/.env.rehearsal`
- Modify: `template/Makefile`

**Interfaces:**
- Consumes: Task 6's Compose file, Caddyfile and `db-init.sql`.
- Produces: `make rehearse-aws`, exit 0 when every check passes. It proves: `db-init.sql` runs and re-runs; `zitadel-init` works with a non-superuser admin over TLS; Zitadel starts from setup; Lago migrates and creates its partitions with the granted rights; Caddy's routing rules. It does **not** prove AWS itself, sign-in in a browser, email, S3 or real certificates.

- [ ] **Step 1: Implement.**

`template/deploy/rehearsal/docker-compose.rehearsal.yml`:

```yaml
# Layers on docker-compose.aws.yml. `db` stands in for RDS: TLS required, and a `dbadmin` that can
# create roles and databases but isn't a superuser. The AWS file's healthy-Lago and Zitadel services run unchanged.
services:
  db:
    image: getlago/postgres-partman:15.0-alpine
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        apk add --no-cache openssl >/dev/null
        openssl req -new -x509 -days 2 -nodes -subj /CN=db -out /tmp/server.crt -keyout /tmp/server.key
        chown postgres /tmp/server.key /tmp/server.crt; chmod 600 /tmp/server.key
        exec docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/tmp/server.crt -c ssl_key_file=/tmp/server.key
    environment: {POSTGRES_USER: postgres, POSTGRES_PASSWORD: rehearsal-superuser}
    tmpfs: [/var/lib/postgresql/data]
    healthcheck: {test: ["CMD", "pg_isready", "-U", "postgres"], interval: 2s, retries: 60}
  caddy:
    environment:
      CADDY_GLOBAL_OPTIONS: local_certs
  zitadel-api:
    depends_on: {db: {condition: service_healthy}}
    environment:
      ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_HOST: ""
  lago-migrate:
    depends_on: {db: {condition: service_healthy}}
```

`template/deploy/rehearsal/.env.rehearsal`. These are throwaway values for a local container, and they're committed on purpose. `.env.rehearsal` is covered by `.env.*` in `.gitignore`, so add `!deploy/rehearsal/.env.rehearsal` there:

```
DOMAIN=rehearsal.localhost
ACME_EMAIL=rehearsal@example.com
DB_HOST=db
ECR_REGISTRY=unused.invalid
BACKEND_TAG=unused
JOBS_TAG=unused
AWS_REGION=us-east-1
DATA_BUCKET=unused
SMTP_HOST=
SES_SMTP_USER=
SES_SMTP_PASSWORD=
ZITADEL_MASTERKEY=rehearsalrehearsalrehearsal12345
ZITADEL_DB_PASSWORD=rehearsal-zitadel
ZITADEL_ADMIN_PASSWORD=Rehearsal-Password-1
LOGIN_SESSION_COOKIE_SECRET=rehearsal-cookie-secret
APP_DB_PASSWORD=rehearsal-app
LAGO_DB_PASSWORD=rehearsal-lago
SECRET_KEY_BASE=rehearsal-rehearsal-rehearsal-rehearsal-rehearsal-rehearsal-rehearsal
LAGO_ENCRYPTION_PRIMARY_KEY=rehearsalrehearsal01
LAGO_ENCRYPTION_DETERMINISTIC_KEY=rehearsalrehearsal02
LAGO_ENCRYPTION_KEY_DERIVATION_SALT=rehearsalrehearsal03
LAGO_API_KEY=rehearsal-lago-key
LAGO_ORG_USER_PASSWORD=rehearsal-lago-user
```

The RSA key is generated at run time by `run.sh`, so that no key-shaped string is in the repo and the template's secret scan stays clean.

`template/deploy/rehearsal/run.sh`:

```bash
#!/bin/bash
# `make rehearse-aws`: the AWS database setup and routing, locally, with no AWS. Leaves nothing behind.
set -euo pipefail
cd "$(dirname "$0")/../.."
project=rehearsal-aws
workdir="$(mktemp -d)"
envfile="$workdir/env"
cp deploy/rehearsal/.env.rehearsal "$envfile"
echo "LAGO_RSA_PRIVATE_KEY=$(openssl genrsa 2048 2>/dev/null | openssl base64 -A)" >> "$envfile"
mkdir -p .bootstrap/zitadel .bootstrap/backend
compose() {
  docker compose -p "$project" --env-file "$envfile" \
    -f docker-compose.aws.yml -f deploy/rehearsal/docker-compose.rehearsal.yml "$@"
}
cleanup() { compose --profile setup down -v --remove-orphans >/dev/null 2>&1 || true; rm -rf "$workdir"; }
trap cleanup EXIT
fail() { echo "REHEARSAL FAILED: $1" >&2; compose logs --tail=60 >&2 || true; exit 1; }

compose up -d --wait db redis

psql_as() {
  compose exec -T -e PGPASSWORD="$2" -e PGSSLMODE=require db psql -v ON_ERROR_STOP=1 -h db -U "$1" "${@:3}"
}

echo "== stand-in for the RDS admin"
psql_as postgres rehearsal-superuser -d postgres \
  -c "CREATE ROLE dbadmin LOGIN PASSWORD 'rehearsal-admin' CREATEDB CREATEROLE;"

echo "== db-init.sql, twice (pg_partman creation needs rds_superuser: postgres plays that role here)"
for _ in 1 2; do
  psql_as postgres rehearsal-superuser -d postgres \
    -v app_password=rehearsal-app -v lago_password=rehearsal-lago < deploy/db-init.sql
done

echo "== Zitadel init as the non-superuser admin"
DB_ADMIN_PASSWORD=rehearsal-admin compose --profile setup run --rm zitadel-init \
  || fail "zitadel-init doesn't work with a non-superuser admin over TLS"

echo "== start Zitadel, Lago and Caddy"
compose up -d --no-deps caddy
compose up -d --wait --wait-timeout 300 zitadel-api || fail "Zitadel didn't become healthy"
compose up -d --wait --wait-timeout 300 lago-api lago-pdf || fail "Lago didn't become healthy"

echo "== Lago created its partitions"
count="$(psql_as lago rehearsal-lago -d lago -Atc "SELECT count(*) FROM partman.part_config;")"
[ "$count" -ge 1 ] || fail "partman.part_config is empty: Lago skipped partitioning"

echo "== routing"
status() { compose exec -T caddy wget -q -S --no-check-certificate -O /dev/null --header "Host: $1" "https://127.0.0.1$2" 2>&1 \
  | awk '/HTTP\//{print $2; exit}'; }
check() {
  got="$(status "$1" "$2" || true)"
  [ "$got" = "$3" ] || fail "https://$1$2 answered '$got', expected $3"
}
check lago.rehearsal.localhost / 403
check lago-api.rehearsal.localhost /api/v1/plans 403
webhook="$(status lago-api.rehearsal.localhost /webhooks/stripe/none)"
[ "$webhook" != 403 ] || fail "Lago's webhooks are blocked"
check auth.rehearsal.localhost /debug/ready 200

echo "== memory, to confirm the server size"
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep "$project" || true
echo "REHEARSAL PASSED"
```

If `wget` with SNI fails because `Host` differs from the connection name, use `curl` from a one-shot `curlimages/curl:8` container on the same network, with `--resolve name:443:<caddy>` and `-k`. Caddy picks certificates by SNI, so `--resolve` is the reliable form. Prefer it from the start if the first run shows a TLS error.

Add to `template/Makefile`:

```make
rehearse-aws:
	bash deploy/rehearsal/run.sh
```

- [ ] **Step 2: Run it.** `make dev && cd .dev/acme && make rehearse-aws`. Expected: `REHEARSAL PASSED`. Expect to fix real problems here. Likely ones: `.env` quoting of values with spaces, `zitadel init` needing an extra privilege, or Lago needing more partman grants. Fix them in the template files, not in the rehearsal. If a fix changes `db-init.sql` grants or Zitadel's commands, record it in this plan as a dated note.

- [ ] **Step 3: Record memory.** Add the `docker stats` total to the Task 13 notes. If the total with all services running is over 6 GB of `t3.large`'s 8 GB, change the default `instance_type` and note why.

- [ ] **Step 4: Commit.**

```bash
git add template/deploy template/Makefile template/.gitignore
git commit -m "feat(infra): local rehearsal of the AWS database setup and routing"
```

---

### Task 12: Runbook and README

**Amendments, 2026-11-01** (from checking this plan against `feat/two-products`, before any code ran. These override the steps and code below. Later fixes found by running the code are added here too.)

- "To go back": the OIDC role only trusts `refs/heads/main`, so `gh workflow run` from an earlier commit is refused. Document only `aws ssm send-command --document-name <slug>-deploy --instance-ids <id> --parameters service=backend,tag=<tag>`.
- "The server failed": `cd infra && terraform plan -replace=aws_instance.server -out=tfplan`, then `make infra-apply`. Drop "point DNS again": the Elastic IP moves with the apply.
- "Database": say plainly that switching production to a restored instance isn't automated in this milestone. Restoring and reading from it is what's documented and tested.
- "Removing a product": Terraform shows two plans, and you confirm each one.

**Files:**
- Create: `template/infra/README.md` (replacing the stub)
- Modify: `template/README.md.jinja`, `template/CLAUDE.md.jinja`, `tests/test_infra_template.py`

**Interfaces:**
- Produces: the only document a person needs to deploy a product. Task 13 follows it.

- [ ] **Step 1: Write the failing test.** Add to `tests/test_infra_template.py`:

```python
def test_runbook_covers_every_step_in_order(product_dir: pathlib.Path) -> None:
    text = (product_dir / "infra" / "README.md").read_text()
    order = ["make infra-init", "make infra-plan", "make infra-apply", "make infra-secrets",
             "make infra-release", "make infra-bootstrap", "make infra-doctor"]
    positions = [text.index(step) for step in order]
    assert positions == sorted(positions)
    for needed in ["destroy", "replace", "SES", "sandbox", "Product", "make infra-destroy", "restore"]:
        assert needed in text, needed
```

- [ ] **Step 2: Run it to see it fail.** `uv run pytest tests/test_infra_template.py -q -k runbook`. Expected: FAIL.

- [ ] **Step 3: Write the runbook.** `template/infra/README.md`:

````markdown
# Deploying to AWS

One server plus a managed database. About $100 to $120 a month per product (estimate; see the top-level README for a measured number once one exists).

## You need

- An AWS account and a profile for it. Check it's the right one: `aws sts get-caller-identity`.
- A domain with a Route 53 hosted zone in that account.
- Terraform 1.17, Docker, uv and the AWS CLI.
- This product pushed to its own GitHub repo.

## First deploy

```bash
export AWS_PROFILE=<your profile>
```

1. Fill in `infra/terraform.tfvars`. For a second product in the same AWS account, also set `create_github_oidc_provider = false`.
2. `make infra-init` creates the Terraform state bucket.
3. `make infra-plan`, and read it. Look for `destroy` and `replace`; on a first deploy, there should be neither.
4. `make infra-apply`. It waits for DNS and certificates, which can take several minutes. It prints two `gh variable set` commands. Run them.
5. Confirm the alarm email subscription from your inbox.
6. `make infra-secrets` generates the app's secrets. Running it again never changes an existing value.
7. `make infra-release` builds the images and uploads the deploy files.
8. `make infra-bootstrap` sets up the databases, Zitadel and Lago, and starts everything.
9. Deploy the frontend: `gh workflow run deploy-frontend`.
10. `make infra-doctor` checks DNS, HTTPS, routing and Lago's partitioning.

Your app is at `https://app.<domain>`.

## Email

Sign-up sends verification email through Amazon SES. New accounts are in the SES **sandbox**, which only delivers to addresses you've verified: verify yours in the SES console before testing sign-up. Request production access before real users arrive.

## Budget alert

The monthly budget counts by the `Product` tag, which only works once you activate `Product` as a cost allocation tag under AWS Billing. Activation can take a day.

## Deploying changes

Merging to `main` deploys only the folder that changed: `frontend/`, `backend/` or `jobs/`. A failed backend release leaves the old version running. Migrations must stay compatible with the previous version, because a rollback doesn't undo them.

To go back: `gh workflow run deploy-backend` from the earlier commit, or run the `<slug>-deploy` SSM document with the earlier tag.

To change `docker-compose.aws.yml`, `deploy/`, or Zitadel and Lago versions: edit them, `make infra-release`, then restart with an SSM session: `sudo systemctl restart app`.

To change infrastructure: `make infra-plan`, read it, `make infra-apply`. A merge never changes infrastructure.

## Getting into the server

```bash
aws ssm start-session --target $(cd infra && terraform output -raw server_instance_id)
```

There's no SSH. Lago's admin screen is closed by default: add your IP to `admin_cidrs` and apply to open it.

## When something's wrong

- **The server failed:** AWS tries to recover it, and emails you. If it's gone for good, `terraform apply -replace=aws_instance.server` through a saved plan, then point DNS again with the same apply. Secrets and tokens come back automatically. Queued background work in Redis can be lost.
- **Database:** to restore, use the RDS console's "restore to point in time" to create a new instance, then read from it to confirm. To switch to it, update `DB_HOST` by importing the new instance into Terraform. Backups are kept for 7 days.
- **Certificates or DNS:** `make infra-doctor` says which host is wrong.

## Stripe

Billing is off until you add a test key: `make infra-set-stripe-key`, then `make infra-bootstrap`. Live keys are refused.

## Removing a product

`make infra-destroy` asks you to type the product's slug, then deletes everything, including the database and its backups. Check AWS Billing a day later.
````

Add one paragraph to `template/README.md.jinja`, under a new `## Deploying`, linking to `infra/README.md`. Add to `template/CLAUDE.md.jinja`:

```markdown
## AWS

`infra/` and `deploy/` run this product on AWS (`infra/README.md`). Agents may run `make infra-plan` and `make infra-doctor`; a person runs every other `make infra-*` command, and the guard enforces this. Migrations must stay compatible with the previous version, because a rollback doesn't undo them.
```

- [ ] **Step 4: Run all checks.** `uv run pytest -q` and `uv run pytest -q -m slow` at the repo root. Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add template/infra/README.md template/README.md.jinja template/CLAUDE.md.jinja tests/test_infra_template.py
git commit -m "docs(infra): deploy runbook"
```

---

### Task 13: The real deploy (James, with an agent observing)

An agent can't do this task, by the guard and by the rules on AWS writes. It needs the AWS account and domain James will provide, and it costs real money. Each numbered step needs James's go-ahead. An agent may read `make infra-plan` and `make infra-doctor` output and fix template bugs found on a branch.

**Files:**
- Modify: `template/README.md.jinja` (measured numbers), this plan (dated notes)

- [ ] **Step 1: Deploy.** Generate a test product, then follow `infra/README.md`, First deploy.

- [ ] **Step 2: Check spec §1 items 1 and 2.** Sign up at `https://app.<domain>` with an SES-verified address, create a workspace, confirm the branding, and open the plans page. Change one frontend file, merge, and confirm the backend's container start time is unchanged.

- [ ] **Step 3: Check things the rehearsal couldn't.**
  - Lago can write to S3 with the server's role. On the server: `docker compose exec lago-api bin/rails runner 'ActiveStorage::Blob.service.upload("rehearsal-check", StringIO.new("x")); puts "ok"'`. If this fails, the fallback is a dedicated IAM user whose key is in `<slug>/app`, passed as `LAGO_AWS_S3_ACCESS_KEY_ID` and `LAGO_AWS_S3_SECRET_ACCESS_KEY`.
  - The budget's `cost_filter` value in the plan reads `user:Product$<slug>`.
  - The disk alarm's dimensions match the real device (`nvme0n1p1` and `xfs`) in CloudWatch. If the alarm shows "insufficient data", correct them.

- [ ] **Step 4: Replace the server.** Terminate it in the console. Rebuild it with `terraform plan -replace=aws_instance.server -out=tfplan`, then `make infra-apply`. Confirm you can still sign in with the same user and see the same workspace.

- [ ] **Step 5: Restore the database.** Restore to a new instance from the RDS console, connect from the server, count rows in `app.workspaces`, and delete the new instance.

- [ ] **Step 6: Remove it.** `make infra-destroy`. The next day, confirm with AWS Billing and the console that nothing billable is left.

- [ ] **Step 7: Record.** Put the measured monthly cost and the time from `copier copy` to live in `template/README.md.jinja`. Note any template fixes here as dated notes, then commit.

```bash
git add template/README.md.jinja docs/superpowers/plans/2026-11-01-boilerplate-milestone-2-aws.md
git commit -m "docs(infra): measured cost and time from the real deploy"
```
