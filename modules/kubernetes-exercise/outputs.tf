output "namespace" {
  description = "Dedicated namespace managed by this Terraform state."
  value       = local.namespace_name
}
output "resource_keys" {
  description = "Stable Kind/name keys, useful while reviewing plans and replacements."
  value       = sort(keys(local.objects))
}
output "diagnostic_pod" {
  description = "The optional in-cluster HTTP client, removed during Terraform destroy."
  value       = var.create_diagnostic_pod ? "arcade-diagnostics" : null
}
