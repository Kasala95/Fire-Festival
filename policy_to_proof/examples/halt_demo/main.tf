# Demo Terraform for Policy-to-Proof.
# Deliberately contains: a planted secret, a wildcard IAM policy, an unencrypted
# RDS instance, and an S3 bucket without server-side encryption — alongside some
# COMPLIANT resources so PASS paths are exercised too.

provider "aws" {
  region = "us-east-1"
}

# --- PLANTED SECRET (triggers SECRET_EXPOSED -> halt) ---------------------
resource "aws_db_instance" "app_db" {
  identifier        = "app-db"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  username          = "admin"
  password          = "SuperSecretP@ssw0rd123"   # hardcoded credential
  storage_encrypted = false                       # unencrypted at rest
}

# AKIA-style access key planted in a local (gitleaks-style hit)
locals {
  aws_access_key_id     = "AKIAIOSFODNN7EXAMPLE"
  aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}

# --- WILDCARD IAM (triggers IAM-LP CONTROL_FAILED) ------------------------
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

# --- S3 bucket WITHOUT encryption (ENC violation) -------------------------
resource "aws_s3_bucket" "raw_data" {
  bucket = "fire-festival-raw-data"
}

# --- EBS volume WITHOUT encryption (ENC violation) ------------------------
resource "aws_ebs_volume" "scratch" {
  availability_zone = "us-east-1a"
  size              = 40
  encrypted         = false
}

# ==========================================================================
# COMPLIANT resources below (these should yield PASS proofs)
# ==========================================================================

# Access logging: CloudTrail + VPC flow log present
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

# KMS key reference (positive proof for secrets management)
resource "aws_kms_key" "data" {
  description             = "data encryption key"
  deletion_window_in_days = 30
}

# Scoped IAM policy (proof of least privilege done right)
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

# Encrypted RDS (proof of encryption at rest)
resource "aws_db_instance" "reporting_db" {
  identifier        = "reporting-db"
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true
  kms_key_id        = aws_kms_key.data.arn
}
