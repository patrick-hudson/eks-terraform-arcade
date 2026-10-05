run "stable_service_contract" {
  command = plan
  assert {
    condition     = length(terraform_data.service) == 2 && terraform_data.service["api"].input.memory_mib == 256 && terraform_data.service["worker"].input.memory_mib == 512
    error_message = "Instances must use service names as keys and retain the request."
  }
}

run "reordered_input_preserves_named_allocations" {
  command = plan
  variables {
    services = [
      { name = "worker", memory_mib = 512 },
      { name = "api", memory_mib = 256 }
    ]
  }
  assert {
    condition     = length(terraform_data.service) == 2 && terraform_data.service["api"].input.memory_mib == 256 && terraform_data.service["worker"].input.memory_mib == 512
    error_message = "Reordering input must preserve both named addresses and requested allocations."
  }
}

run "empty_service_set_rejected" {
  command = plan
  variables { services = [] }
  expect_failures = [var.services]
}

run "unaligned_memory_rejected" {
  command = plan
  variables { services = [{ name = "api", memory_mib = 65 }] }
  expect_failures = [var.services]
}

run "invalid_identifier_rejected" {
  command = plan
  variables { services = [{ name = "Bad_Name", memory_mib = 256 }] }
  expect_failures = [var.services]
}

run "per_service_limit_rejected" {
  command = plan
  variables { services = [{ name = "api", memory_mib = 2112 }] }
  expect_failures = [var.services]
}

run "duplicate_identity_rejected" {
  command = plan
  variables {
    services = [
      { name = "api", memory_mib = 256 },
      { name = "api", memory_mib = 512 }
    ]
  }
  expect_failures = [var.services]
}

run "oversubscription_rejected" {
  command = plan
  variables {
    services = [
      { name = "api", memory_mib = 2048 },
      { name = "worker", memory_mib = 2048 },
      { name = "batch", memory_mib = 64 }
    ]
  }
  expect_failures = [var.services]
}
