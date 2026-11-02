resource "aws_route53_record" "server" {
  for_each = toset(["auth", "api", "lago", "lago-api"])
  zone_id  = var.route53_zone_id
  name     = "${each.key}.${var.domain}"
  type     = "A"
  ttl      = 300
  records  = [aws_eip.server.public_ip]
}
