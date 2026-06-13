# Full-pipeline demo (NO planted secret, so the run does NOT halt).
# Exercises FAIL + PASS + N_A paths so the full evidence packet renders:
# wildcard IAM (FAIL), unencrypted S3/RDS/EBS (FAIL), but CloudTrail/flow logs
# and an encrypted RDS + KMS reference (PASS proofs).

provider "aws" {
  region = "us-east-1"
}

# --- WILDCARD IAM (IAM-LP -> FAIL + remediation diff) ---------------------
resource "aws_iam_policy" "too_broad" {
  name = "too-broad"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# --- Unencrypted storage (ENC -> FAIL + INSECURE_DEFAULT) -----------------
resource "aws_s3_bucket" "raw_data" {
  bucket = "fire-festival-raw-data"
}

resource "aws_ebs_volume" "scratch" {
  availability_zone = "us-east-1a"
  size              = 40
  encrypted         = false
}

resource "aws_db_instance" "app_db" {
  identifier        = "app-db"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = false
}

# ===================== COMPLIANT (PASS proofs) ============================

resource "aws_cloudtrail" "org_trail" {
  name                  = "org-trail"
  is_multi_region_trail = true
  s3_bucket_name        = aws_s3_bucket.raw_data.id
}

resource "aws_flow_log" "vpc" {
  vpc_id          = "vpc-12345678"
  traffic_type    = "ALL"
  log_destination = aws_s3_bucket.raw_data.arn
}

resource "aws_kms_key" "data" {
  description             = "data encryption key"
  deletion_window_in_days = 30
}

resource "aws_iam_policy" "scoped" {
  name = "scoped-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "arn:aws:s3:::fire-festival-raw-data/*"
    }]
  })
}

resource "aws_db_instance" "reporting_db" {
  identifier        = "reporting-db"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true
  kms_key_id        = aws_kms_key.data.arn
}
