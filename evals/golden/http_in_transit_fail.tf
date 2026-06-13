# ENC in-transit FAIL: plaintext HTTP listener on port 80.
resource "aws_lb_listener" "web" {
  load_balancer_arn = "arn:aws:elasticloadbalancing:us-east-1:111:loadbalancer/app"
  port              = 80
  protocol          = "HTTP"
}
