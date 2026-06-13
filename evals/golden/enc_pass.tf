# ENC should PASS: RDS + EBS encrypted at rest, S3 SSE configured.
resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = true
  kms_key_id        = "arn:aws:kms:us-east-1:111:key/abc"
}

resource "aws_ebs_volume" "vol" {
  availability_zone = "us-east-1a"
  size              = 20
  encrypted         = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  bucket = "app-bucket"
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}
