# riddled.tf — a deliberately INSECURE Terraform file for the Policy-to-Proof demo.
# Paste this into the dashboard's "Paste my own Terraform" box and run a scan.
# It fails almost every control on purpose, so the verdict is a loud NO-SHIP.
#
# What's wrong here (and which control catches it):
#   - wildcard IAM policy        -> IAM-LP  (least privilege)   FAIL
#   - unencrypted RDS / EBS / S3 -> ENC     (encryption)        FAIL
#   - plaintext HTTP listener    -> ENC     (in transit)        FAIL
#   - no CloudTrail / flow logs  -> AC-LOG  (access logging)    FAIL
#
# To ALSO trigger the dramatic SECRET_EXPOSED *halt* (the run stops immediately,
# before any control can even be checked), add a hardcoded AWS access key and a
# password literal to the locals block below. We deliberately leave those OUT here
# so this file shows the FULL failing matrix instead of halting on the first secret.

locals {
  region = "us-east-1"
}

# ---- Least privilege: WILDCARD everything (very bad) ----------------------
resource "aws_iam_policy" "god_mode" {
  name = "god-mode"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# ---- Encryption at rest: all OFF ------------------------------------------
resource "aws_db_instance" "db" {
  identifier        = "prod-db"
  engine            = "postgres"
  instance_class    = "db.t3.large"
  storage_encrypted = false
}

resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 500
  encrypted         = false
}

resource "aws_s3_bucket" "uploads" {
  bucket = "company-customer-uploads"
  # no server-side encryption configured
}

# ---- Encryption in transit: plaintext HTTP --------------------------------
resource "aws_lb_listener" "public" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:111111111111:loadbalancer/app/prod"
  port              = 80
  protocol          = "HTTP"
}

# ---- Compute with no logging anywhere on the account ----------------------
resource "aws_instance" "web" {
  ami           = "ami-0123456789abcdef0"
  instance_type = "t3.large"
}
