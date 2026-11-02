# Deploying to AWS

One server plus a managed database. About $100 to $120 a month per product (an estimate: nothing here has been measured on AWS yet).

Nothing in this folder has been proven on a real AWS account. `make rehearse-aws` (below) covers the database setup and routing locally; the first real deploy is the first test of everything else. Read each plan before you apply it.

## You need

- An AWS account and a profile for it. Check it's the right one: `aws sts get-caller-identity`.
- A domain with a Route 53 hosted zone in that account.
- Terraform 1.17, Docker, uv and the AWS CLI.
- This product pushed to its own GitHub repo.
- Room in the account's quotas. Each product uses one VPC and one Elastic IP, and AWS allows 5 VPCs and 5 Elastic IPs per region by default. The region's default VPC counts too, so that's about four products per region until you request more under Service Quotas.

## First deploy

```bash
export AWS_PROFILE=<your profile>
```

1. Fill in `infra/terraform.tfvars` and commit it. The make commands and Terraform refuse the placeholder `github_repo` and `example.com` or `example.org` addresses. For a second product in the same AWS account, also set `create_github_oidc_provider = false`. The first product then owns the account's GitHub OIDC provider, and destroying it breaks the others until you set `create_github_oidc_provider = true` on a surviving product and apply (see "Removing a product").
2. `make infra-init` creates the Terraform state bucket.
3. `make infra-plan`, and read it. Look for `destroy` and `replace`; on a first deploy, there should be neither.
4. `make infra-apply`. It waits for DNS and certificates, which can take several minutes. It prints two `gh variable set` commands. Run them.
5. Confirm the alarm email subscription from your inbox.
6. `make infra-secrets` generates the app's secrets. Running it again never changes an existing value.
7. `make infra-release` builds the images, writes their tags to SSM and uploads the deploy files. This first release is the only time it builds images. `infra/terraform.tfvars` must be committed by now, because it refuses a dirty tree.
8. `make infra-bootstrap` sets up the databases, Zitadel and Lago, and starts everything.
9. Deploy the frontend: `gh workflow run deploy-frontend`.
10. `make infra-doctor` checks the deployment (see "What `make infra-doctor` checks").

Your app is at `https://app.<domain>`.

### Before the first `make infra-bootstrap`: check the pg_partman version

Lago's first migration calls `pg_partman` with `p_type := 'range'`, which needs pg_partman 5 or later. The local rehearsal ran 5.4.0. RDS may offer a different version, and RDS is only reachable from the server, so run the check there. After `make infra-release` (which uploads `deploy/`), open a session on the server:

```bash
aws ssm start-session --target $(cd infra && terraform output -raw server_instance_id)
```

Then, in that session:

```bash
sudo -i
set -a; . /etc/app.env; set +a
export PATH="$PATH:/usr/local/bin" HOME="${HOME:-/root}"
app-start || { echo 'app-start failed: stop here'; exit 1; }
cd /opt/app
val() { grep "^$1=" .env | cut -d= -f2-; }
export PGPASSWORD="$(aws secretsmanager get-secret-value --secret-id "$(val DB_ADMIN_SECRET_ARN)" --query SecretString --output text | jq -er .password)"
docker run --rm -e PGPASSWORD -e PGSSLMODE=require postgres:15-alpine \
  psql -h "$(val DB_HOST)" -U dbadmin -d postgres -c "SELECT default_version FROM pg_available_extensions WHERE name = 'pg_partman'"
unset PGPASSWORD
```

The password is read from Secrets Manager on the server and passed to the container through the environment, so it never appears in a command line or a file. If `app-start` printed an error, stop and fix that first. If the version is below 5, stop: Lago's migration is expected to fail.

After `make infra-bootstrap`, `lago-api` is running and the same question can be asked through it: `cd /opt/app && COMPOSE_FILE=docker-compose.aws.yml docker compose exec -T lago-api bin/rails runner '...'` with a query against the database `lago` connects to. `make infra-doctor` already does this for the partman row (below).

## What `make infra-doctor` checks

It exits 1 and prints a `PROBLEM:` line for each of these that fails:

- DNS: `auth.`, `api.`, `lago.` and `lago-api.<domain>` all point at the server's address.
- HTTPS answers: `auth.<domain>/debug/ready`, `api.<domain>/health` and `app.<domain>/` return 200. A missing answer usually means the certificate isn't issued yet because DNS isn't pointing at the server.
- Lago stays closed: `lago.` and `lago-api.<domain>` return 403 while `admin_cidrs` is empty. With `admin_cidrs` set, `lago.` may also return 200 and `lago-api.` 401 or 403. Only Lago's webhooks are meant to be public.
- On the server, through SSM: all eleven services are running (`caddy`, `redis`, `zitadel-api`, `zitadel-login`, `lago-api`, `lago-worker`, `lago-clock`, `lago-front`, `lago-pdf`, `backend`, `jobs`). Caddy answers 403 for Lago even when Lago is down, so this check matters.
- On the server: `partman.part_config` in Lago's database has a row for `public.enriched_events`. If not, Lago's first migration didn't set up partitioning: see `docker compose logs lago-migrate` on the server.

It does not check email delivery, Stripe, or that a sign-up works end to end.

## Email

Sign-up sends verification email through Amazon SES. New accounts are in the SES **sandbox**, which only delivers to addresses you've verified: verify yours in the SES console before testing sign-up. Request production access before real users arrive.

## Budget alert

The monthly budget counts by the `Product` tag, which only works once you activate `Product` as a cost allocation tag under AWS Billing. Activation can take a day.

## Deploying changes

Merging to `main` deploys only the folder that changed: `frontend/`, `backend/` or `jobs/`. A failed backend release leaves the old version running. Migrations must stay compatible with the previous version, because a rollback doesn't undo them.

To go back, run the deploy SSM document with the earlier image tag. `service` is `backend` or `jobs`. The tag is the 12-character short commit SHA the deploy workflow used (`git rev-parse --short=12 <commit>`); the document accepts 7 to 40 hex characters. ECR keeps only the last 20 images per repository, so a tag from long ago may be gone, and then the pull fails and the current version keeps running.

```bash
aws ssm send-command --document-name <slug>-deploy \
  --instance-ids $(cd infra && terraform output -raw server_instance_id) \
  --parameters service=backend,tag=<tag> \
  --query Command.CommandId --output text
```

That prints a command id and returns at once; the deploy runs on the server. Read the result with:

```bash
aws ssm get-command-invocation --command-id <id> \
  --instance-id $(cd infra && terraform output -raw server_instance_id) \
  --query '[Status,StandardOutputContent,StandardErrorContent]'
```

Repeat until `Status` is no longer `InProgress`. It can wait up to 10 minutes for another deploy to release the deploy lock before it starts.

Going back across a release that added a database migration fails, and fails safely. `deploy.sh` runs `alembic upgrade head` from the older image, which doesn't know the newer revision, so the migration step errors, the script exits 1 and the current version keeps running. The fix is to roll forward: deploy a new commit that fixes the problem. A rollback only works when no migration was added since the tag you go back to.

`gh workflow run` can't do this: the deploy role only trusts the `main` branch, so a run from an earlier commit is refused.

### Changing `docker-compose.aws.yml`, `deploy/`, or the Zitadel and Lago versions

Edit them, merge to `main`, and from an up-to-date `main` run `make infra-release`, because the server gets whatever your checkout holds. Once image tags exist, it uploads the deploy files only, leaves images and tags alone, and says so. The backend and jobs move only through the deploy workflows, which migrate, check health and roll back. Then, in an SSM session: `sudo systemctl restart app`.

The restart fetches the deploy files, rebuilds `.env` from Secrets Manager and SSM, pulls, and runs `docker compose up -d`, which recreates only containers whose image or settings changed. What that means:

- **The backend and jobs stay safe.** They restart on the tags in SSM, so it is the same code on the same schema, with no migration to run.
- **Everything else gets no health check and no rollback.** This covers a new Zitadel or Lago version, which also run their own migrations as they start. Run `make rehearse-aws` first and `make infra-doctor` after. A migration isn't undone by editing the version back.
- **Caddy doesn't pick up a changed `Caddyfile` by itself:** Compose doesn't see inside the file. After the restart: `cd /opt/app && COMPOSE_FILE=docker-compose.aws.yml docker compose up -d --force-recreate caddy`.
- **Don't restart during a deploy:** the restart doesn't take the deploy lock. And if a deploy ended with `deployed but not recorded`, redeploy first, because the restart and every reboot use the tag in SSM.
- **If the restart reports a failure, it's still retrying.** `systemctl` says the job failed at the first failed try, but the service tries again every minute and never gives up. Read `journalctl -u app`, and use `sudo systemctl stop app` to end the retries. The same retries cover boot, so a registry outage during a server replacement clears by itself.

To change infrastructure: `make infra-plan`, read it, `make infra-apply`. A merge never changes infrastructure.

## Rehearsal: `make rehearse-aws`

Runs the AWS database setup and Lago/Zitadel routing on your own machine, against a Postgres that stands in for RDS (non-superuser admin, TLS required). It runs `deploy/db-init.sql` twice, Zitadel's init, Lago's migrations (and again on a migrated database), checks that Lago created its partitions and that Caddy routes the way "What `make infra-doctor` checks" expects, with and without `admin_cidrs`. It removes what it starts.

It proves the SQL, the compose file and the routing work against a Postgres of that shape. It does not prove anything about AWS: not RDS itself, IAM, SSM, SES, DNS, certificates or the Terraform. In particular it ran as a stand-in superuser for the one step RDS does as `rds_superuser`.

No workflow runs it. Run it by hand whenever the Lago or Zitadel image version in `docker-compose.aws.yml` changes.

## Lago's migrations and `structure.sql`

On an empty database Rails loads Lago's `db/structure.sql` instead of running the migrations. That file drops and recreates `pg_partman`, which fails for a non-superuser such as `lago`, and it would leave `partman.part_config` empty. So the `lago-migrate` service deletes `db/structure.sql` and runs all the migrations. Check this still holds whenever you upgrade Lago: does the new version still ship `structure.sql`, and do its migrations still set up `pg_partman` without it? `make rehearse-aws` and `make infra-doctor` both look for the `part_config` row.

## Open decision: partition maintenance

Lago v1.55.0 never calls pg_partman's `run_maintenance`, and nothing here does either. Lago creates partitions once, at first migrate, for about 3 months ahead. After that no new partitions are created, rows land in the default partition, and retention doesn't run. Nothing fails and `make infra-doctor` stays green. Whether to schedule maintenance (and how) is not decided and nothing has been built for it. Decide before the product is about 3 months old.

## Getting into the server

```bash
aws ssm start-session --target $(cd infra && terraform output -raw server_instance_id)
```

There's no SSH. Lago's admin screen is closed by default: add your IP to `admin_cidrs` and apply to open it.

## When something's wrong

- **The server failed:** AWS tries to recover it, and emails you. A server that stops reporting at all, such as one that was terminated, triggers the `server-unhealthy` email after about 10 minutes. A new server also sends that email once just after it starts, because it has no data yet; the alarm clears by itself. If it's gone for good: `cd infra && terraform plan -replace=aws_instance.server -out=tfplan`, read the plan, then `make infra-apply`. The Elastic IP moves with the apply, so DNS stays right. Secrets and tokens come back automatically. Queued background work in Redis can be lost. Then run `make infra-doctor`.
- **Database:** RDS availability, failure, failover and low-storage events are emailed to `alert_email`. To restore, use the RDS console's "restore to point in time" to create a new instance, then read from it to confirm. Switching production to the restored instance isn't automated in this milestone. Backups are kept for 7 days. A restored instance is yours to delete: Terraform doesn't know about it, it's billed until you do, and it can block `make infra-destroy`.
- **Certificates or DNS:** `make infra-doctor` says which host is wrong.

## Stripe

Billing is off until you add a test key: `make infra-set-stripe-key`, then `make infra-bootstrap`. Live keys are refused.

## Removing a product

`make infra-destroy` asks you to type the product's slug, then runs two Terraform plans (the first turns off deletion protection, the second destroys), and you confirm each one. It deletes everything it created, including the database, its backups, the image tags in SSM and the state bucket, so deploying the slug again starts fresh. Check AWS Billing a day later.

It leaves two things:

- **The Route 53 hosted zone,** which a person created (about $0.50 a month). Delete it in the console if the domain is finished with.
- **A database you restored,** which Terraform doesn't know about. If one exists, delete it first: it keeps billing, and if it uses this product's subnet group, it makes `terraform destroy` fail.

**If other products share this account:** when `create_github_oidc_provider` is true, as on the first product, destroying this product deletes the account's GitHub OIDC provider, and `make infra-destroy` warns you. Every other product's deploys then fail at the AWS sign-in step, and their `terraform plan` fails looking up the provider. To recover, after the destroy finishes, set `create_github_oidc_provider = true` in one surviving product's `infra/terraform.tfvars`, then run `make infra-plan` and `make infra-apply` there. The provider's ARN is the same, so the other products need no change.
