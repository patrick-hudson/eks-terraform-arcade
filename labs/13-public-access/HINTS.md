# Progressive hints

## Hint 1 · Find where requests stop

Compare four observations: pod readiness, localhost HTTP, Service HTTP from a different pod, and public HTTP from your laptop. If the first three work, list the extra steps the laptop request must pass through. Capture the failure before changing anything.

## Hint 2 · Read every port in the path

The Service has three related but different fields. Which port does a packet arriving at the node's public IPv4 use? Which field selects the container's listener? A security group checks packets at its attached network interface; it does not read the Service definition.

## Hint 3 · Compare the Terraform rule to the Service

Inspect `allowed_port` in `access/main.tf` and `nodePort` in `workload/candidate.yaml`. Keep the Service fixed for this incident. Make one source edit and require a Terraform plan that affects only `aws_vpc_security_group_ingress_rule.laptop`.

## If the repair still times out

Read your current source address with the same direct IPv4 network path as the external probe. Compare it with the rule's `/32`. Check the node public IPv4 against a fresh preflight. Corporate networks can block high destination ports; moving networks also requires updating Game 07's API `/32` through Terraform before Kubernetes checks will work. Do not solve it by opening every port or the whole internet.
