output "aws_region" { value = var.aws_region }
output "database_secret_arn" { value = aws_db_instance.main.master_user_secret[0].secret_arn }
output "data_bucket" { value = aws_s3_bucket.data.id }
output "deploy_bucket" { value = aws_s3_bucket.deploy.id }
output "ecr_backend_url" { value = aws_ecr_repository.backend.repository_url }
output "ecr_jobs_url" { value = aws_ecr_repository.jobs.repository_url }
output "app_secret_name" { value = aws_secretsmanager_secret.app.name }
output "bootstrap_secret_name" { value = aws_secretsmanager_secret.bootstrap.name }
