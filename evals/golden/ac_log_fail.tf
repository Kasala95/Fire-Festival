# AC-LOG should FAIL: no CloudTrail, no flow logs, no access logging.
resource "aws_s3_bucket" "data" {
  bucket = "app-bucket"
}

resource "aws_instance" "web" {
  ami           = "ami-123"
  instance_type = "t3.micro"
}
