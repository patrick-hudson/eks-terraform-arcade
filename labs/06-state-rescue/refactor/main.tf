resource "aws_cloudwatch_log_group" "service" {
  name              = "/arcade/${var.lab_id}/state-rescue"
  retention_in_days = 1
  tags              = { Owner = "terraform" }
}
moved {
  from = aws_cloudwatch_log_group.app
  to   = aws_cloudwatch_log_group.service
}
output "log_group" { value = aws_cloudwatch_log_group.service.name }
