# Genuine-plan developer fixture: built-in provider only, no provisioners/backend.
terraform {
  required_version = ">= 1.5.0"
}

variable "input_value" {
  type    = string
  default = "initial"
}

variable "replacement_key" {
  type    = string
  default = "initial"
}

resource "terraform_data" "payload" {
  input = var.input_value
}

resource "terraform_data" "delete_first" {
  triggers_replace = [var.replacement_key]
}

resource "terraform_data" "create_first" {
  triggers_replace = [var.replacement_key]
  lifecycle {
    create_before_destroy = true
  }
}

resource "terraform_data" "legacy" {
  input = "keep this object"
}
