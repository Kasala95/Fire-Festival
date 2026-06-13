# Malformed HCL: unbalanced braces. Must not crash; parser is best-effort.
resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = false
  nested {
    broken = "value"
# missing closing braces intentionally
