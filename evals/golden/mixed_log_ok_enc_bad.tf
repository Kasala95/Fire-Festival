# Mixed: logging present (AC-LOG pass) but encryption off (ENC fail).
resource "aws_cloudtrail" "main" {
  name                  = "org-trail"
  is_multi_region_trail = true
}

resource "aws_flow_log" "vpc" {
  vpc_id       = "vpc-123"
  traffic_type = "ALL"
}

resource "aws_db_instance" "db" {
  identifier        = "app-db"
  storage_encrypted = false
}
