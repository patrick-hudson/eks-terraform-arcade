locals {
  bucket_arn = "arn:aws:s3:::${var.lab_id}-${var.expected_account_id}-policy-demo"
}
variable "policy_variant" {
  type    = string
  default = "fixed"
  validation {
    condition     = contains(["broken", "fixed"], var.policy_variant)
    error_message = "Choose broken or fixed."
  }
}
resource "aws_iam_policy" "boundary" {
  name = "${var.lab_id}-04-boundary"
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["s3:GetObject"], Resource = "${local.bucket_arn}/published/*"
  }] })
}
resource "aws_iam_role" "reader" {
  name                 = "${var.lab_id}-04-reader"
  permissions_boundary = aws_iam_policy.boundary.arn
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" }
  }] })
}
resource "aws_iam_role_policy" "read" {
  name = "read-one-prefix"
  role = aws_iam_role.reader.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Action = ["s3:GetObject"],
    Resource = var.policy_variant == "broken" ? local.bucket_arn : "${local.bucket_arn}/*"
  }] })
}
output "role_arn" { value = aws_iam_role.reader.arn }
output "role_name" { value = aws_iam_role.reader.name }
output "bucket_arn" { value = local.bucket_arn }
output "boundary_arn" { value = aws_iam_policy.boundary.arn }
