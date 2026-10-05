variable "manifest_path" {
  description = "Local multi-document YAML containing exactly one dedicated arcade Namespace and its resources."
  type        = string
  validation {
    condition     = fileexists(var.manifest_path)
    error_message = "manifest_path must name an existing candidate YAML file."
  }
}

variable "extra_manifest_paths" {
  description = "Optional local YAML files, such as a Terraform-managed fixture ConfigMap. Do not duplicate the Namespace."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for path in var.extra_manifest_paths : fileexists(path)])
    error_message = "Every extra manifest file must exist before planning."
  }
}

variable "create_diagnostic_pod" {
  description = "Create a token-free, restricted Alpine Pod for read-only in-cluster HTTP checks."
  type        = bool
  default     = true
}
