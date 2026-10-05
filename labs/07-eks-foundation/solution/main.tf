variable "admin_principal_arn" {
  description = "Permanent IAM role/user ARN used by your AWS CLI; never an STS session ARN."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/.+$", var.admin_principal_arn))
    error_message = "Use a permanent IAM user or role ARN, not arn:aws:sts::...:assumed-role/... ."
  }
}
variable "allowed_cidr" {
  description = "Your current public IPv4 address plus /32, for the public Kubernetes API."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && can(regex("/32$", var.allowed_cidr))
    error_message = "Supply one IPv4 /32 CIDR, for example 203.0.113.10/32; do not use that example address."
  }
}
variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

data "aws_availability_zones" "available" {
  state            = "available"
  exclude_zone_ids = ["use1-az3"]
  filter {
    name   = "zone-type"
    values = ["availability-zone"]
  }
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required", "opted-in"]
  }
}
locals {
  name     = "${var.lab_id}-arcade"
  zone_ids = slice(sort(data.aws_availability_zones.available.zone_ids), 0, 2)
  addons   = toset(["vpc-cni", "kube-proxy", "coredns", "eks-pod-identity-agent"])
}
resource "aws_vpc" "lab" {
  cidr_block           = "10.77.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = local.name }
}
resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.lab.id
  availability_zone_id    = local.zone_ids[count.index]
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index)
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.name}-public-${count.index}" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_iam_role" "cluster" {
  name = "${local.name}-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}
resource "aws_eks_cluster" "lab" {
  name                          = local.name
  role_arn                      = aws_iam_role.cluster.arn
  version                       = var.kubernetes_version
  bootstrap_self_managed_addons = true
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }
  upgrade_policy {
    support_type = "STANDARD"
  }
  vpc_config {
    subnet_ids              = aws_subnet.public[*].id
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = [var.allowed_cidr]
  }
  depends_on = [aws_iam_role_policy_attachment.cluster, aws_route_table_association.public]
}
resource "aws_eks_access_entry" "admin" {
  cluster_name  = aws_eks_cluster.lab.name
  principal_arn = var.admin_principal_arn
  type          = "STANDARD"
}
resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = aws_eks_cluster.lab.name
  principal_arn = aws_eks_access_entry.admin.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
}
resource "aws_iam_role" "node" {
  name = "${local.name}-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}
resource "aws_launch_template" "node" {
  name_prefix   = "${local.name}-"
  instance_type = "t3.medium"
  credit_specification {
    cpu_credits = "standard"
  }
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type           = "gp3"
      volume_size           = 20
      encrypted             = true
      delete_on_termination = true
    }
  }
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = local.name, Project = "aws-interview-arcade", Lab = "07", LabId = var.lab_id }
  }
  tag_specifications {
    resource_type = "volume"
    tags          = { Project = "aws-interview-arcade", Lab = "07", LabId = var.lab_id }
  }
}
resource "aws_eks_node_group" "lab" {
  cluster_name    = aws_eks_cluster.lab.name
  node_group_name = "lab"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.public[*].id
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }
  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }
  update_config {
    max_unavailable = 1
  }
  labels     = { role = "lab" }
  depends_on = [aws_iam_role_policy_attachment.node]
}
# Bootstrap networking before nodes join, then adopt the core add-ons as managed add-ons.
data "aws_eks_addon_version" "core" {
  for_each           = local.addons
  addon_name         = each.value
  kubernetes_version = aws_eks_cluster.lab.version
  most_recent        = true
}
resource "aws_eks_addon" "core" {
  for_each                    = local.addons
  cluster_name                = aws_eks_cluster.lab.name
  addon_name                  = each.value
  addon_version               = data.aws_eks_addon_version.core[each.key].version
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.lab]
}
output "cluster_name" { value = aws_eks_cluster.lab.name }
output "region" { value = var.region }
output "vpc_id" { value = aws_vpc.lab.id }
output "node_role_arn" { value = aws_iam_role.node.arn }
output "cluster_security_group_id" { value = aws_eks_cluster.lab.vpc_config[0].cluster_security_group_id }
output "node_group_name" { value = aws_eks_node_group.lab.node_group_name }
