resource "terraform_data" "service" {
  for_each = var.services
  input    = each.value
}

output "allocations" {
  value = { for name, service in terraform_data.service : name => service.output.memory_mib }
}
