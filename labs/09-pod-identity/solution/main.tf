variable "cluster_name" { type = string }
resource "aws_s3_bucket" "fixture" {
  bucket_prefix = "${var.lab_id}-arcade-09-"
  force_destroy = true
}
resource "aws_s3_bucket_public_access_block" "fixture" {
  bucket                  = aws_s3_bucket.fixture.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "fixture" {
  bucket = aws_s3_bucket.fixture.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_object" "fixture" {
  bucket                 = aws_s3_bucket.fixture.id
  key                    = "allowed/message.txt"
  content                = "pod-identity-works\n"
  server_side_encryption = "AES256"
}
resource "aws_iam_role" "reader" {
  name = "${var.lab_id}-arcade-reader"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
      Condition = {
        StringEquals = {
          "aws:RequestTag/kubernetes-namespace"       = "arcade-identity"
          "aws:RequestTag/kubernetes-service-account" = "reader"
        }
      }
    }]
  })
}
resource "aws_iam_role_policy" "reader" {
  role = aws_iam_role.reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = ["s3:GetObject"], Resource = aws_s3_object.fixture.arn
    }]
  })
}
resource "aws_eks_pod_identity_association" "reader" {
  cluster_name    = var.cluster_name
  namespace       = "arcade-identity"
  service_account = "reader"
  role_arn        = aws_iam_role.reader.arn
  depends_on      = [aws_iam_role_policy.reader]
}
output "bucket_name" { value = aws_s3_bucket.fixture.id }
output "reader_role_arn" { value = aws_iam_role.reader.arn }
