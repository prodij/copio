# Connector credentials use envelope encryption (backend/app/connectors/vault.py and
# jobs/jobs/sync/credentials.py): each credential gets its own data key from this KMS key, and only the
# wrapped data key is stored next to the ciphertext. The default key policy leaves access to IAM, so the
# server role below is the only principal (with the account's admins) that can use it.
resource "aws_kms_key" "connectors" {
  description             = "${local.name} connector credentials (envelope encryption)"
  key_usage               = "ENCRYPT_DECRYPT"
  enable_key_rotation     = true
  deletion_window_in_days = var.protect ? 30 : 7
}

resource "aws_kms_alias" "connectors" {
  name          = "alias/${local.name}-connectors"
  target_key_id = aws_kms_key.connectors.key_id
}

# The backend and jobs containers run on the one server and share its role. Both seal (GenerateDataKey)
# and open (Decrypt), and only with the vault's encryption context, so the key can't be used as a
# general-purpose decryption oracle from that role.
resource "aws_iam_role_policy" "server_connector_kms" {
  name = "${local.name}-connector-kms"
  role = aws_iam_role.server.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
      Resource = aws_kms_key.connectors.arn
      Condition = {
        StringEquals = { "kms:EncryptionContext:purpose" = "connector-credential" }
      }
    }]
  })
}
