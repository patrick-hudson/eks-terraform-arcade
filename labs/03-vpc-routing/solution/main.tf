data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  zones = {
    a = { name = data.aws_availability_zones.available.names[0], index = 0 }
    b = { name = data.aws_availability_zones.available.names[1], index = 1 }
  }
}

resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.lab_id}-routing" }
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = "${var.lab_id}-routing" }
}

resource "aws_subnet" "public" {
  for_each                = local.zones
  vpc_id                  = aws_vpc.lab.id
  availability_zone       = each.value.name
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, each.value.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.lab_id}-public-${each.key}", Tier = "public" }
}

resource "aws_subnet" "private" {
  for_each                = local.zones
  vpc_id                  = aws_vpc.lab.id
  availability_zone       = each.value.name
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, each.value.index + 10)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.lab_id}-private-${each.key}", Tier = "private" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = "${var.lab_id}-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.lab.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = local.zones
  vpc_id   = aws_vpc.lab.id
  tags     = { Name = "${var.lab_id}-private-${each.key}" }
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

output "vpc_id" {
  value = aws_vpc.lab.id
}

output "public_subnet_ids" {
  value = { for key, subnet in aws_subnet.public : key => subnet.id }
}

output "private_subnet_ids" {
  value = { for key, subnet in aws_subnet.private : key => subnet.id }
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_ids" {
  value = { for key, rt in aws_route_table.private : key => rt.id }
}

output "subnet_cidrs" {
  value = {
    public  = { for key, subnet in aws_subnet.public : key => subnet.cidr_block }
    private = { for key, subnet in aws_subnet.private : key => subnet.cidr_block }
  }
}
