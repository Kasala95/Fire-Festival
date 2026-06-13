# ENC should FAIL: EBS volume not encrypted.
resource "aws_ebs_volume" "vol" {
  availability_zone = "us-east-1a"
  size              = 50
  encrypted         = false
}
