terraform {
  required_version = ">= 1.16.5, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.67.0"
    }
  }
}

variable "region" {
  type    = string
  default = "us-west-2"
}
variable "aws_profile" {
  description = "The explicit AWS CLI profile used for Game 07 and the ownership preflight."
  type        = string
  validation {
    condition     = length(trimspace(var.aws_profile)) > 0
    error_message = "Supply the profile used for this lab."
  }
}
variable "expected_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Supply the intended lab account ID (12 digits)."
  }
}
variable "lab_id" {
  description = "The SAME lab_id used to build Game 07."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,15}$", var.lab_id))
    error_message = "Use the Game 07 lab_id (3-16 lowercase letters, numbers or hyphens)."
  }
}
provider "aws" {
  region              = var.region
  profile             = var.aws_profile
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project = "aws-interview-arcade"
      Lab     = "13"
      LabId   = var.lab_id
    }
  }
}
