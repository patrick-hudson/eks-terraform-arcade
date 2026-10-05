variable "region" {
  type    = string
  default = "us-west-2"
}
variable "aws_profile" {
  description = "Explicit named AWS CLI profile, also used by the Kubernetes token command."
  type        = string
  validation {
    condition     = length(trimspace(var.aws_profile)) > 0
    error_message = "Set TF_VAR_aws_profile to the profile used for this lab."
  }
}
variable "expected_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be the intended 12-digit AWS account ID."
  }
}
variable "cluster_name" {
  description = "Name of the existing Game 07 EKS cluster; never inferred from current kubeconfig."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", var.cluster_name))
    error_message = "Provide the existing EKS cluster name."
  }
}
variable "extra_manifest_paths" {
  description = "Optional YAML paths relative to this workload directory, e.g. fixture.yaml."
  type        = list(string)
  default     = []
}
variable "create_diagnostic_pod" {
  type    = bool
  default = true
}
