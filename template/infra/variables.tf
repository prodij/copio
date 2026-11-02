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
