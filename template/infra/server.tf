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
  # insecure_value: `.value` is sensitive, which would hide the AMI in the plan a person has to read.
  ami                    = data.aws_ssm_parameter.al2023.insecure_value
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
  instance   = aws_instance.server.id
  domain     = "vpc"
  depends_on = [aws_internet_gateway.main]
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
