provider "aws" {
  region              = var.region
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
}

# The cluster must already exist. Keep AWS infrastructure and Kubernetes workloads
# in different Terraform states so a missing control plane cannot block its destroy.
data "aws_eks_cluster" "lab" { name = var.cluster_name }

provider "kubernetes" {
  host                   = data.aws_eks_cluster.lab.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.lab.certificate_authority[0].data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.region, "--profile", var.aws_profile, "--output", "json"]
  }
}

module "exercise" {
  source                = "./workload-module"
  manifest_path         = "${path.module}/candidate.yaml"
  extra_manifest_paths  = [for path in var.extra_manifest_paths : "${path.module}/${path}"]
  create_diagnostic_pod = var.create_diagnostic_pod
}

output "namespace" { value = module.exercise.namespace }
output "resource_keys" { value = module.exercise.resource_keys }
output "diagnostic_pod" { value = module.exercise.diagnostic_pod }
