# Weak posture (no secret): wildcard IAM + unencrypted RDS/EBS + no logging.
resource "aws_iam_policy" "admin" {
  name = "admin"
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = false
}

resource "aws_ebs_volume" "vol" {
  availability_zone = "us-east-1a"
  size              = 100
  encrypted         = false
}
