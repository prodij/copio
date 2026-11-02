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
