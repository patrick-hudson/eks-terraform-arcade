variable "table_environment_key" {
  type    = string
  default = "TABLE_NAME"
}
resource "aws_dynamodb_table" "counter" {
  name         = "${var.lab_id}-05-counter"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  attribute {
    name = "pk"
    type = "S"
  }
}
resource "aws_cloudwatch_log_group" "counter" {
  name              = "/aws/lambda/${var.lab_id}-05-counter"
  retention_in_days = 1
}
resource "aws_iam_role" "lambda" {
  name = "${var.lab_id}-05-lambda"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" }
  }] })
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = aws_dynamodb_table.counter.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.counter.arn}:*" }
  ] })
}
data "archive_file" "code" {
  type        = "zip"
  source_file = "${path.module}/handler.py"
  output_path = "${path.module}/lambda.zip"
}
resource "aws_lambda_function" "counter" {
  function_name    = "${var.lab_id}-05-counter"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.14"
  architectures    = ["x86_64"]
  timeout          = 5
  memory_size      = 128
  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256
  environment { variables = { (var.table_environment_key) = aws_dynamodb_table.counter.name } }
  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.counter]
}
output "function_name" { value = aws_lambda_function.counter.function_name }
output "table_name" { value = aws_dynamodb_table.counter.name }
output "log_group" { value = aws_cloudwatch_log_group.counter.name }
