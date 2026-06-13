# SECRET_EXPOSED: hardcoded AWS key + DB password -> critical halt before any PASS.
locals {
  aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1"
}

resource "aws_db_instance" "db" {
  identifier = "app-db"
  password   = "SuperSecretP@ssw0rd123"
}
