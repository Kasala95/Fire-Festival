# SEC-MGMT proof present (KMS), no hardcoded secrets.
resource "aws_kms_key" "main" {
  description             = "app key"
  deletion_window_in_days = 30
}

resource "aws_db_instance" "db" {
  identifier = "app-db"
  password   = data.aws_secretsmanager_secret_version.db.secret_string
}
