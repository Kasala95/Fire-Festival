# Strong posture: logging + encryption + scoped IAM + KMS. Best-case run.
resource "aws_cloudtrail" "main" {
  name                  = "org-trail"
  is_multi_region_trail = true
}

resource "aws_flow_log" "vpc" {
  vpc_id       = "vpc-123"
  traffic_type = "ALL"
}

resource "aws_kms_key" "main" {
  description = "app key"
}

resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = true
  kms_key_id        = "arn:aws:kms:us-east-1:111:key/abc"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sse" {
  bucket = "app-bucket"
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_iam_policy" "scoped" {
  name = "scoped"
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "arn:aws:s3:::app-bucket/*"
    }]
  })
}
