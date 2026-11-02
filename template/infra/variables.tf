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
  # scripts/infra.py's check_placeholders applies the same rules before it touches AWS.
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+$", var.github_repo)) && !startswith(lower(var.github_repo), "owner/")
    error_message = "Set github_repo to this product's real org/name. The deploy role trusts that repo, and anyone holding the placeholder's GitHub account could create it."
  }
}
variable "alert_email" {
  type = string
  validation {
    condition     = !can(regex("[@.]example\\.(com|org)$", lower(var.alert_email)))
    error_message = "Set alert_email to a real address. Alarms go there, and it is the contact for the HTTPS certificates."
  }
}
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
