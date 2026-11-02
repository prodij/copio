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
