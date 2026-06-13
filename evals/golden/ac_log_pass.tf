# AC-LOG should PASS: CloudTrail + VPC flow logs + S3 access logging present.
resource "aws_cloudtrail" "main" {
  name                       = "org-trail"
  is_multi_region_trail      = true
  enable_log_file_validation = true
}

resource "aws_flow_log" "vpc" {
  vpc_id          = "vpc-123"
  traffic_type    = "ALL"
  log_destination = "arn:aws:logs:us-east-1:111:log-group:flow"
}

resource "aws_s3_bucket_logging" "logs" {
  bucket        = "app-bucket"
  target_bucket = "log-bucket"
  target_prefix = "s3/"
}
