variable "cluster_name" { type = string }
data "aws_eks_cluster" "lab" { name = var.cluster_name }
data "aws_eks_addon_version" "ebs" {
  addon_name         = "aws-ebs-csi-driver"
  kubernetes_version = data.aws_eks_cluster.lab.version
  most_recent        = true
}
resource "aws_iam_role" "ebs" {
  name = "${var.lab_id}-arcade-ebs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
      Condition = {
        StringEquals = {
          "aws:RequestTag/kubernetes-namespace"       = "kube-system"
          "aws:RequestTag/kubernetes-service-account" = "ebs-csi-controller-sa"
        }
      }
    }]
  })
}
data "aws_iam_policy" "ebs" {
  name = "AmazonEBSCSIDriverPolicyV2"
}
resource "aws_iam_role_policy_attachment" "ebs" {
  role       = aws_iam_role.ebs.name
  policy_arn = data.aws_iam_policy.ebs.arn
}
resource "aws_eks_addon" "ebs" {
  cluster_name                = var.cluster_name
  addon_name                  = "aws-ebs-csi-driver"
  addon_version               = data.aws_eks_addon_version.ebs.version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  pod_identity_association {
    role_arn        = aws_iam_role.ebs.arn
    service_account = "ebs-csi-controller-sa"
  }
  depends_on = [aws_iam_role_policy_attachment.ebs]
}
output "addon_version" { value = aws_eks_addon.ebs.addon_version }
output "csi_role_arn" { value = aws_iam_role.ebs.arn }
