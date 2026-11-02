# Boilerplate milestone 2: AWS deployment

Date: 2026-11-01. Status: design, awaiting review. Builds on [milestone 1](2026-10-30-boilerplate-milestone-1-design.md).

## 1. Goal

The boilerplate is the product. Copio is one example of what gets built with it.

Milestone 1 generates a product that runs on one machine. Milestone 2 makes the same product run on AWS:

> `copier copy`, set a few values, run the documented commands, and the product is live on HTTPS with sign-in working. It survives losing its server with no data lost, and it can be removed cleanly.

**Done means**, on a real AWS account and domain:

1. A freshly generated product goes live on HTTPS, and you can sign up, create a workspace, see its branding, and open the plans page.
2. A frontend-only deploy leaves the backend untouched.
3. Replacing the server loses no data held in RDS, S3 or Secrets Manager.
4. A database restore from backup has been done once.
5. `make infra-destroy` removes everything, and nothing billable is left.
6. The measured monthly cost and the time from `copier copy` to live are recorded in the template's README.

Payments aren't part of this. They stay unproven until a real Stripe test key is used.

## 2. Assumptions to correct

- Cost matters, because there will be many products, some with no users.
- A few minutes of downtime is acceptable until a product has paying customers.
- The AWS account and domain arrive later. They are values in one file, so all design and code can proceed without them. Only the real deploy (§10) waits on them.

## 3. Decisions

| # | Decision | Rejected, and why |
|---|---|---|
| M1 | One EC2 server running Compose, plus RDS Postgres, per product | One server only: data dies with the server, and backups become our job. Fargate, ElastiCache and a load balancer: two to three times the cost, and a second way of running everything |
| M2 | x86 server | ARM: `getlago/lago-gotenberg:7.8.2` is x86 only, so production would stop running the exact pinned images |
| M3 | Jobs stay in the scheduler container on the server, keeping their `handler(event, context)` shape and raw-first S3 storage. **Changes milestone 1's D7**, which planned Lambda and EventBridge | Lambda: jobs need the private database and the internet, which means a NAT gateway per product |
| M4 | Frontend on S3 and CloudFront | Serving it from the server: frontend deploys would touch the server |
| M5 | Caddy on the server handles HTTPS | Load balancer: a fixed monthly cost per product for one target |
| M6 | Terraform is applied only by a person, from a saved plan | Apply on merge: a merge shouldn't be able to destroy a database |
| M7 | App deploys run in CI on merge, per folder, signing in to AWS with OIDC | Stored AWS keys in GitHub |
| M8 | Secrets live in Secrets Manager, and Terraform only knows their names | Passing them through Terraform: they end up in state |
| M9 | One flat `infra/` folder per product, with no shared modules | Shared modules: couples products, against D1 |
| M10 | Every resource name starts with the product slug, and the provider has `allowed_account_ids` | Depending on one account per product. Products can share an account now and split later, and a wrong profile fails instead of deploying |
| M11 | Separate `docker-compose.aws.yml`; the local file stays as it is | One file with conditionals: the two differ in credentials, HTTPS, storage and exposed ports, and a mistake could weaken production |
| M12 | Email through Amazon SES over SMTP | No email: password reset and email verification don't work |

Terraform is pinned to `~> 1.17` and the AWS provider to `~> 6.71` (latest on 2026-11-01: 1.17.1 and 6.71.0), with `.terraform.lock.hcl` committed. This machine has Terraform 1.16.0, so it needs upgrading first.

## 4. Architecture

```
                         Internet
             ┌──────────────┴───────────────┐
         app.<domain>            api. / auth. / lago. / lago-api.<domain>
             │                              │
       ┌─────▼──────┐              ┌────────▼─────────────────────┐
       │ CloudFront │              │ EC2 server, no SSH           │
       │ + S3       │              │  Caddy: HTTPS, ports 80, 443 │
       │ frontend   │              │  backend, jobs scheduler     │
       └────────────┘              │  Zitadel API + login         │
                                   │  Lago API, worker, clock,    │
                                   │  front, PDF                  │
                                   │  Redis                       │
                                   └───────┬───────────────┬──────┘
                                           │               │
                                   ┌───────▼──────┐  ┌─────▼─────┐
                                   │ RDS Postgres │  │ S3 raw    │
                                   │ app, zitadel,│  │ data and  │
                                   │ lago, no     │  │ files     │
                                   │ public IP    │  └───────────┘
                                   └──────────────┘
```

The subdomains are `auth.`, `lago.` and `lago-api.`, matching the local stack, rather than the `billing.` shown during design.

**Network:** one VPC with public subnets for the server and private subnets for RDS. No NAT gateway. The server's firewall allows only 80 and 443 in; admins reach it through Session Manager.

**Server:** Amazon Linux with Docker, encrypted disk, metadata service v2 only, and log rotation. An instance role grants only what it needs: this product's secrets, S3 bucket and ECR repositories. It starts as `t3.large`; the size is confirmed by measuring (§10).

**Database:** one single-zone RDS Postgres 15 instance, matching the local major version, holding databases `app`, `zitadel` and `lago`. Reachable only from the server. Backups kept 7 days, deletion protection on, final snapshot on delete.

**Files:** one S3 bucket, versioned and private. Real S3 replaces SeaweedFS by leaving `S3_ENDPOINT_URL` unset, which the job code already supports.

**Redis:** stays on the server. Queued background work can be lost if the server is lost. `billing_reconcile` recovers subscription state afterwards.

**What's public on `lago-api.` and `lago.`:** only `lago-api.<domain>/webhooks/*` is public, because Stripe must reach it. Lago's UI and the rest of its API are limited by Caddy to the `admin_cidrs` list, and the backend reaches Lago over the internal Compose network. An empty list means no outside access, and an admin uses a Session Manager port forward instead.

**No Stripe CLI and no mock payments:** `stripe-cli` isn't in the AWS file, and milestone 1's mock payment path can't be enabled in this configuration, which a test enforces. Billing stays off until a key is added, using milestone 1's no-Stripe mode.

## 5. Values a product sets

`infra/terraform.tfvars`, committed, holds no secrets:

| Value | Purpose |
|---|---|
| `aws_account_id` | Goes in `allowed_account_ids` |
| `aws_region` | Default `us-west-2` |
| `domain` | Parent domain. Milestone 1's `.localhost` Copier value stays for local use |
| `route53_zone_id` | The hosted zone holding the domain. Creating or registering the domain is a human step |
| `github_repo` | Which repo may deploy through OIDC |
| `alert_email` | Alarms and budget alerts |
| `monthly_budget_usd` | Budget alert threshold |
| `admin_cidrs` | Who can open Lago's UI. Default empty |
| `instance_type` | Default `t3.large` |
| `use_staging_certificates` | Let's Encrypt's staging service, for repeated rebuild tests that would hit rate limits |

The AWS profile is passed by the person running the command and is never committed.

## 6. Commands

| Command | What it does |
|---|---|
| `make infra-init` | Once per product: creates the state bucket, then initializes Terraform with S3 state and S3 native locking |
| `make infra-secrets` | Generates app secrets into Secrets Manager. Never overwrites an existing one |
| `make infra-plan` | Prints the target account, then saves a plan |
| `make infra-apply` | Applies exactly the saved plan |
| `make infra-bootstrap` | Runs database setup and the existing bootstrap on the server, through Session Manager |
| `make infra-doctor` | Checks DNS, certificates, service health, Zitadel, Lago and `pg_partman` |
| `make infra-destroy` | Removes everything after you type the product slug. Deletion protection is switched off by a separate, visible plan first |

The template's agent guard blocks agents from `infra-apply`, `infra-destroy` and Terraform `apply` or `destroy`. Agents can run `infra-plan`.

## 7. App deploys

Each folder deploys on its own, on merge to `main`, when its path changes.

| Folder | Steps |
|---|---|
| `frontend/` | Build, copy to S3, clear CloudFront. Public build values are read from SSM parameters that bootstrap writes |
| `backend/` | Build, push to ECR with the commit as tag, then a deploy script on the server through SSM Run Command: pull, run migrations in a one-shot container, start the new version, check health |
| `jobs/` | Same as backend, without a public health check |

- **Failures:** if a migration or health check fails, the previous version keeps running or is restarted, and CI goes red.
- **Rollback:** redeploy an earlier tag. A migration isn't undone, so migrations must stay compatible with the previous version. This goes in the product's agent instructions.
- **Downtime:** a few seconds during a backend restart.
- **Zitadel and Lago:** pinned in `docker-compose.aws.yml`, and changed only by deliberately editing the version.
- **CI's permissions:** ECR push, this product's frontend bucket, CloudFront invalidation, and running the one deploy document on this server. No Terraform and no secrets.

## 8. Secrets

| Secret | Created by | Used by |
|---|---|---|
| RDS admin password | RDS (`manage_master_user_password`) | Database setup only |
| Per-service database passwords, Zitadel master key, Lago keys | `make infra-secrets` | Server, at startup |
| Zitadel admin and login tokens | Written by Zitadel on first start, then saved by bootstrap | Bootstrap, backend |
| SES SMTP credentials | `make infra-secrets` | Zitadel |
| Stripe key | Pasted by you when ready | Bootstrap |

- The server renders them to a root-only `.env` on its encrypted disk at startup. They exist on that disk while the server runs.
- **Zitadel's tokens must be saved.** Zitadel creates them only on its first start against an empty database. Locally they sit in `.bootstrap/`. On AWS, a replaced server would otherwise have no way to get them back.
- Only `sk_test_` keys are accepted in this milestone, as locally. Going live is a later checklist (§12).

## 9. Failures

| What goes wrong | What happens | How you find out |
|---|---|---|
| Server hardware fails | CloudWatch auto-recovers it to new hardware | Alarm email |
| Server lost for good | `make infra-apply` builds a new one; startup restores secrets and services, and Caddy gets new certificates. Queued Redis work can be lost | Alarm email |
| Disk nearly full | Log rotation makes this unlikely | Alarm email |
| Database lost or corrupted | Restore from backup | Alarm email on RDS health and storage |
| Bad backend deploy or migration | Previous version keeps running | CI |
| Certificate can't be issued | Usually DNS isn't pointing at the server yet; `make infra-doctor` says so | `make infra-doctor` |
| `pg_partman` missing | Lago's migration silently skips its setup, so `make infra-doctor` fails on this explicitly | `make infra-doctor` |
| Costs run away | Budget alert | Alarm email |
| Wrong AWS profile | Terraform refuses, because of `allowed_account_ids` | Command fails |
| Accidental database destroy | Deletion protection blocks it, and the plan shows it first | Plan output |

The biggest risk is `make infra-apply` replacing the server or database. The plan shows this before anything happens, and the README tells the reader to look for `destroy` and `replace`.

## 10. Testing

**On every template PR, with no AWS account or cost:**

- `terraform fmt -check` and `terraform validate` on a freshly generated product
- `docker compose config` on `docker-compose.aws.yml`
- Tests for: no `stripe-cli` or mock payment path in the AWS file; no secret values in `infra/`; every resource name includes the slug; the guard blocks agent applies; and Caddy's rules keep Lago private except for webhooks

**The real test, once the account and domain are provided, each step approved by you:**

1. Generate a product and deploy it.
2. Check items 1 and 2 of §1.
3. Terminate the server, rebuild it, and confirm sign-in and data are still there.
4. Restore the database from backup to a new instance and read from it.
5. Run `make infra-destroy`, and confirm with the AWS console and billing that nothing is left.
6. Record the measured cost and time.

Measure memory on the running local stack before this, to confirm the server size.

## 11. Cost

Rough estimates from memory, not yet checked against AWS pricing: about $100 to $120 a month per product. That covers an x86 server around $60, a small RDS instance around $30, and disk, DNS and alerts. CloudFront and S3 stay small at low traffic. Step 6 of §10 replaces this with a measured number. Server size may change it, because the memory use of all the containers together hasn't been measured.

## 12. Out of scope

| Item | When |
|---|---|
| Multiple availability zones, load balancing, autoscaling | When a product has customers who need it. Everything is in containers, so one product can move to Fargate alone |
| Jobs on Lambda | When a product's jobs are heavy enough to affect the server |
| Staging environment | Deploy a second copy with another slug if needed |
| Firewall (WAF) | Before public launch of a product that needs it |
| SES production access | Requested per product before real users. The sandbox can only send to verified addresses, which is enough for the test |
| Live Stripe keys, sales tax | A go-live checklist, before taking real payments |
| Registering domains | Human step |

## 13. To verify while planning

These are facts about upstream tools to check, not open design choices:

- Lago's file storage settings for S3, so invoices survive a server replacement
- RDS's default TLS requirement, and the connection settings Zitadel and Lago need for it
- The database privileges Zitadel and Lago need, especially to create `pg_partman`, on an RDS admin role that isn't a true superuser
- Zitadel's settings for running behind Caddy on HTTPS, and for SMTP and email verification
- The template's current guard rules, so the new ones extend them
- How the frontend gets its build values once `feat/run-without-stripe` is merged

## 14. Depends on

Milestone 1's `feat/run-without-stripe` must be merged first, because the first deploy runs with billing off.
