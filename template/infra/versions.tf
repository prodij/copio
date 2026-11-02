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
