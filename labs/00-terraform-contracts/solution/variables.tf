terraform {
  required_version = ">= 1.16.5, < 2.0"
}

variable "services" {
  description = "Stable service identity plus its requested memory, in MiB."
  type = list(object({
    name       = string
    memory_mib = number
  }))
  default = [
    { name = "api", memory_mib = 256 },
    { name = "worker", memory_mib = 512 }
  ]
  validation {
    condition     = length(var.services) > 0 && length(distinct([for s in var.services : s.name])) == length(var.services)
    error_message = "Supply at least one service and use unique service names."
  }
  validation {
    condition     = alltrue([for s in var.services : can(regex("^[a-z][a-z0-9-]+$", s.name))])
    error_message = "Service names must begin with a letter and contain lowercase letters, digits or hyphens."
  }
  validation {
    condition     = alltrue([for s in var.services : s.memory_mib >= 64 && s.memory_mib <= 2048 && s.memory_mib % 64 == 0])
    error_message = "Each request must be a multiple of 64 MiB between 64 and 2048 MiB."
  }
  validation {
    condition     = sum(concat([0], [for s in var.services : s.memory_mib])) <= 4096
    error_message = "The shared memory budget is 4096 MiB."
  }
}
