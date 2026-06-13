# ENC should FAIL: RDS storage_encrypted = false.
resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = false
}
