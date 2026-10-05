variable "cluster_name" {
  type = string
  validation {
    condition     = var.cluster_name == "${var.lab_id}-arcade"
    error_message = "This exercise only uses the matching Game 07 arena."
  }
}
variable "node_instance_id" {
  description = "The exact EC2 instance resolved from the Ready Kubernetes node providerID by preflight.sh."
  type        = string
  validation {
    condition     = can(regex("^i-([0-9a-f]{8}|[0-9a-f]{17})$", var.node_instance_id))
    error_message = "Supply an EC2 instance ID from the preflight."
  }
}
variable "allowed_cidr" {
  description = "The current public IPv4 /32 of the laptop running the external curl probe."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && can(regex("/32$", var.allowed_cidr))
    error_message = "Allow one IPv4 /32 only. Do not open 0.0.0.0/0."
  }
}
variable "allowed_port" {
  description = "The TCP destination port permitted from the learner's laptop. Diagnose the required value."
  type        = number
  default     = 30081
  validation {
    condition     = contains([30080, 30081], var.allowed_port)
    error_message = "This exercise is bounded to port 30080 or 30081."
  }
}

data "aws_eks_cluster" "lab" {
  name = var.cluster_name
}
data "aws_instance" "node" {
  instance_id = var.node_instance_id
}

resource "aws_vpc_security_group_ingress_rule" "laptop" {
  security_group_id = data.aws_eks_cluster.lab.vpc_config[0].cluster_security_group_id
  description       = "Arcade Game 13 temporary laptop HTTP; destroy after exercise"
  cidr_ipv4         = var.allowed_cidr
  ip_protocol       = "tcp"
  from_port         = var.allowed_port
  to_port           = var.allowed_port

  lifecycle {
    precondition {
      condition = (
        data.aws_eks_cluster.lab.status == "ACTIVE" &&
        try(data.aws_eks_cluster.lab.tags["Project"], "") == "aws-interview-arcade" &&
        try(data.aws_eks_cluster.lab.tags["Lab"], "") == "07" &&
        try(data.aws_eks_cluster.lab.tags["LabId"], "") == var.lab_id
      )
      error_message = "Refusing access: cluster is not the active, tagged Game 07 arena."
    }
    precondition {
      condition = (
        data.aws_instance.node.public_ip != "" &&
        contains(data.aws_eks_cluster.lab.vpc_config[0].subnet_ids, data.aws_instance.node.subnet_id) &&
        contains(data.aws_instance.node.vpc_security_group_ids, data.aws_eks_cluster.lab.vpc_config[0].cluster_security_group_id) &&
        try(data.aws_instance.node.tags["Project"], "") == "aws-interview-arcade" &&
        try(data.aws_instance.node.tags["Lab"], "") == "07" &&
        try(data.aws_instance.node.tags["LabId"], "") == var.lab_id &&
        try(data.aws_instance.node.tags["Name"], "") == var.cluster_name
      )
      error_message = "Refusing access: node must have a public IPv4 and match the Game 07 VPC, cluster SG and ownership tags."
    }
  }
}

output "security_group_rule_id" {
  value = aws_vpc_security_group_ingress_rule.laptop.security_group_rule_id
}
output "cluster_security_group_id" {
  value = data.aws_eks_cluster.lab.vpc_config[0].cluster_security_group_id
}
output "public_url" {
  description = "Probe from your laptop, outside the cluster. The Service NodePort is always 30080."
  value       = "http://${data.aws_instance.node.public_ip}:30080/"
}
output "allowed_cidr" {
  value = var.allowed_cidr
}
