# TODO: VPC 10.42.0.0/16, two AZs, public /24s at offsets 0 and 1,
# private /24s at offsets 10 and 11, attached internet gateway,
# one public route table and a private route table per AZ.
# Associate every subnet explicitly. Only the public table gets 0.0.0.0/0.
# Keep map_public_ip_on_launch=false in every subnet.
# Export: vpc_id, public_subnet_ids, private_subnet_ids,
# public_route_table_id, private_route_table_ids, subnet_cidrs.
# No compute, NAT, elastic IPs, endpoints or flow logs in this mission.
