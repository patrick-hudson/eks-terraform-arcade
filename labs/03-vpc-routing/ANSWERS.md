# Answer · explicit subnet associations

The complete `solution/main.tf` creates one VPC, four subnets, one internet gateway, three custom route tables, one internet route and four explicit associations. AWS also creates the VPC's default main route table and other default networking objects; they are not separate resources in this Terraform root. Private subnet route tables have only the implicit local route.

To install the full solution in your existing working root:

```bash
: "${LAB_ROOT:?Set LAB_ROOT to the extracted package directory}"
cd "$LAB_ROOT/run/03-vpc-routing"
cp "$LAB_ROOT/labs/03-vpc-routing/solution/main.tf" main.tf
terraform init
terraform fmt
terraform validate
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
```

Continue with the mission's assertions and teardown. The key route is:

```hcl
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.lab.id
}
```

The route is not enough by itself. Each public subnet must associate with that route table. An IPv4 host also needs a public IPv4 association and permissive security-group/NACL rules for the requested traffic. `map_public_ip_on_launch = false` here does not make the route table private; it controls automatic address assignment for future instances.

An internet-bound IPv4 packet from a public-addressed instance matches the default route; its internet gateway maps the instance's private address to its public address. A destination inside `10.42.0.0/16` matches the more-specific local route. Security groups are stateful; NACLs are stateless and require considering return traffic separately.

The private subnets here are isolated. A NAT gateway is one possible egress design, often one per AZ to reduce cross-AZ dependency and traffic, but adds hourly and data-processing charges. Private service access through VPC endpoints can avoid NAT for specific APIs; endpoint coverage, DNS and any per-endpoint charges must be evaluated. Neither option is built in this game.

The fixed keys protect address identity if iteration order changes. They do not guarantee the physical AZ mapping stays immutable across arbitrary account/region changes. A production module should make the AZ contract explicit and review any replacement plan.
