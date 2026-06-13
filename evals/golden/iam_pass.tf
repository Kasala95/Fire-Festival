# IAM-LP should PASS: scoped JSON policy with quoted keys, no wildcards.
resource "aws_iam_policy" "scoped" {
  name   = "scoped"
  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::app-bucket/data/*"
    }
  ]
}
POLICY
}
