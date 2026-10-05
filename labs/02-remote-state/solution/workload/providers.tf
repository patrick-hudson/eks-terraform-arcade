terraform {
  required_version = ">= 1.16.5, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.67.0, < 7.0"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project = "aws-interview-arcade"
      Lab     = "02"
      LabId   = var.lab_id
    }
  }
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "lab_id" {
  type    = string
  default = "tfeks"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,15}$", var.lab_id))
    error_message = "Use 3-16 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "expected_account_id" {
  description = "Your dedicated lab AWS account, checked before resource operations."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Set the twelve-digit dedicated lab account ID."
  }
}
