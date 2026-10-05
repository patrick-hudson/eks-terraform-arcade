resource "terraform_data" "service" {
  for_each = { for service in var.services : service.name => service }
  input    = each.value
}

output "allocations" {
  value = { for name, service in terraform_data.service : name => service.output.memory_mib }
}
