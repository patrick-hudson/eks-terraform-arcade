resource "aws_cloudwatch_log_group" "app" {
  name              = "/arcade/${var.lab_id}/state-rescue"
  retention_in_days = 1
  tags              = { Owner = "terraform" }
}
output "log_group" { value = aws_cloudwatch_log_group.app.name }
