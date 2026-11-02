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

resource "aws_route53_record" "ses_verification" {
  zone_id = var.route53_zone_id
  name    = "_amazonses.${var.domain}"
  type    = "TXT"
  ttl     = 600
  records = [aws_ses_domain_identity.main.verification_token]
}

resource "aws_ses_domain_identity_verification" "main" {
  domain     = aws_ses_domain_identity.main.id
  depends_on = [aws_route53_record.ses_dkim, aws_route53_record.ses_verification]
}

# `make infra-secrets` creates this user's key and derives the SMTP password. The key lives
# outside Terraform, so force_destroy lets `terraform destroy` delete the user anyway.
resource "aws_iam_user" "ses_smtp" {
  name          = "${local.name}-ses-smtp"
  force_destroy = true
}

resource "aws_iam_user_policy" "ses_smtp" {
  name = "${local.name}-send-email"
  user = aws_iam_user.ses_smtp.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "ses:SendRawEmail"
      Resource  = "*"
      Condition = { StringEquals = { "ses:FromAddress" = "no-reply@${var.domain}" } }
    }]
  })
}
