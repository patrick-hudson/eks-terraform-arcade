# 03 · Routing without a surprise NAT bill

**40–55 minutes · mid-senior · $0 standing infrastructure charge for the specified design.** Build only a VPC, subnets, route tables and an attached internet gateway. Do not create instances, NAT gateways, elastic IPs, interface endpoints, flow logs or load balancers. Those are outside this game and can add charges. [VPC pricing](https://aws.amazon.com/vpc/pricing/).

A team claims “the subnet has public in its name, so internet access should work.” Build enough evidence to evaluate that claim. Use `10.42.0.0/16`, two available AZs, public `/24` subnets at offsets 0 and 1, and private `/24` subnets at offsets 10 and 11. Use stable `a` and `b` keys. Associate both public subnets with one public route table that sends `0.0.0.0/0` to an internet gateway. Associate each private subnet with its own route table, without a default internet route. Explicitly associate all four subnets. Enable VPC DNS support and hostnames.

Keep `map_public_ip_on_launch = false` everywhere. Publicness is about routes; this setting avoids accidentally assigning chargeable public IPv4 addresses to later instances. Export `vpc_id`, `public_subnet_ids`, `private_subnet_ids`, `public_route_table_id`, `private_route_table_ids`, and `subnet_cidrs`. Use maps keyed by `a` and `b` for paired resources.

From the extracted package directory:

```bash
export LAB_ROOT="$(pwd)"
test -d "$LAB_ROOT/labs/03-vpc-routing"
: "${TF_VAR_expected_account_id:?Set the intended dedicated lab account ID first}"
export AWS_REGION="${TF_VAR_region:-us-west-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_VAR_region="$AWS_REGION"
test "$(aws sts get-caller-identity --query Account --output text)" = "$TF_VAR_expected_account_id"
mkdir -p "$LAB_ROOT/run/03-vpc-routing"
cp "$LAB_ROOT/labs/03-vpc-routing/starter/"*.tf "$LAB_ROOT/run/03-vpc-routing/"
cp "$LAB_ROOT/labs/03-vpc-routing/solution/.terraform.lock.hcl" "$LAB_ROOT/run/03-vpc-routing/"
cd "$LAB_ROOT/run/03-vpc-routing"
${EDITOR:-vi} main.tf
terraform init
terraform fmt
terraform validate
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
export VPC_ID="$(terraform output -raw vpc_id)"
terraform output subnet_cidrs
```

The starter contains the provider guard and a resource checklist. Write the network resources before planning. Use [HINTS.md](HINTS.md) incrementally and [ANSWERS.md](ANSWERS.md) when ready for full code.

Run the evidence checks:

```bash
PUBLIC_RT="$(terraform output -raw public_route_table_id)"
aws ec2 describe-route-tables --route-table-ids "$PUBLIC_RT" > public-routes.json
jq -e '[.RouteTables[0].Routes[] | select(.DestinationCidrBlock == "0.0.0.0/0" and ((.GatewayId // "") | startswith("igw-")))] | length == 1' public-routes.json
jq -e '[.RouteTables[0].Associations[] | select(.SubnetId != null)] | length == 2' public-routes.json
for PRIVATE_RT in $(terraform output -json private_route_table_ids | jq -r '.[]'); do
  aws ec2 describe-route-tables --route-table-ids "$PRIVATE_RT" > private-routes.json
  jq -e '[.RouteTables[0].Routes[] | select(.DestinationCidrBlock == "0.0.0.0/0")] | length == 0' private-routes.json
  jq -e '[.RouteTables[0].Associations[] | select(.SubnetId != null)] | length == 1' private-routes.json
done
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" > subnets.json
jq -e '(.Subnets | length == 4) and ([.Subnets[].AvailabilityZone] | unique | length == 2) and ([.Subnets[].MapPublicIpOnLaunch] | all(. == false))' subnets.json
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" |
  jq -e '[.NatGateways[] | select(.State != "deleted")] | length == 0'
terraform plan -detailed-exitcode
# Required: every assertion succeeds and the final plan returns 0.
```

Explain the packet path without deploying a host. A host with only a private IPv4 address in a public subnet cannot use an internet gateway for IPv4 internet access; it also needs an associated public IPv4 address. The private subnets here are deliberately isolated from internet egress. They can still use the VPC's local route, subject to security groups and network ACLs. Names and tags do not change these facts. [Internet gateways](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html), [route tables](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Route_Tables.html).

Senior follow-ups: explain longest-prefix matching; distinguish a route, security group and NACL; describe a same-AZ NAT design and its charges without building it; explain why private EKS nodes still need a path to image registries and required AWS APIs; compare NAT with an endpoint-based design. The EKS game builds its own separate network, so destroy this one before moving on.

```bash
cd "$LAB_ROOT/run/03-vpc-routing"
export VPC_ID="$(terraform output -raw vpc_id)"
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
aws ec2 describe-vpcs --filters "Name=vpc-id,Values=$VPC_ID" |
  jq -e '.Vpcs | length == 0'
terraform show -json | jq -e '[.values.root_module.resources[]? | select(.mode == "managed")] | length == 0'
```

If you stop after a partial apply, preserve state, run destroy and verify the VPC disappears. If an output is absent, use `terraform state show aws_vpc.lab` to recover the ID. If the configuration is invalid, save your attempted code and restore `solution/main.tf` in the same root before destroying. A dependency error usually means something was attached outside the lab; identify that object before acting on it.
