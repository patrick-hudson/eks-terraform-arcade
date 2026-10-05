# Reference diagnosis and repair

The starter opens **TCP 30081**, while `public-demo` listens through **NodePort 30080**. Its process listens on 8080 and its Service port is 80. The internal probes succeed because they do not traverse the laptop-to-node inbound rule. The EKS API endpoint and its allowed source IP ranges are unrelated to this application port.

Edit the copied `access/main.tf` default `allowed_port` from `30081` to `30080`. If you previously set `TF_VAR_allowed_port` or added an `allowed_port` tfvars value, that override wins over the default: correct the active source or unset the override so the plan represents your intended repair. Then:

```bash
: "${LAB13_RUN:?Follow the lab README preparation}"
terraform -chdir="$LAB13_RUN/access" fmt
terraform -chdir="$LAB13_RUN/access" validate
terraform -chdir="$LAB13_RUN/access" plan -out=repair.tfplan
terraform -chdir="$LAB13_RUN/access" show repair.tfplan
terraform -chdir="$LAB13_RUN/access" apply repair.tfplan
export PUBLIC_URL="$(terraform -chdir="$LAB13_RUN/access" output -raw public_url)"
test "$(curl --noproxy '*' -4 -fsS --connect-timeout 5 --max-time 10 "$PUBLIC_URL")" = arcade-public-ok
```

Only the standalone rule may change. Depending on provider behavior, a rule change can be represented as an update or replacement; review the resource identity and scope, not just the numeric plan totals. No cluster, node, full security group, route or existing account resource should change. Leave source restricted to the current laptop's `/32`.

The `solution` directory contains the corrected AWS root and identical healthy workload. Copying a solution over the active state is unnecessary: edit the one source value and preserve state.

## Evidence that earns full credit

1. Baseline: external TCP connection fails while localhost and Service HTTP return the marker.
2. Diagnosis: observed Service NodePort differs from the destination port on the security group rule this lab owns; source and node identity match preflight.
3. Repair: saved Terraform plan changes only that owned rule and retains `/32`; outside-client HTTP returns the exact marker afterward.
4. Cleanup: destroy the rule; API lookup of its exact ID returns NotFound; a fresh outside connection fails while internal Service HTTP still succeeds. Then destroy the Terraform-managed workload and finally Game 07.

Port-forward is useful diagnostics, but cannot substitute for evidence item 3. A timeout alone cannot substitute for the rule identity check: it could also mean your Wi-Fi or node disappeared.

## Additional fault rounds

After the base incident is repaired, keep the narrow correct rule and break one Kubernetes source field at a time. Edit `workload/candidate.yaml`, plan and apply through the workload root, predict evidence, then repair through Terraform before starting the next round.

| Fault | Localhost HTTP | Service from client pod | Laptop public HTTP | Distinguishing evidence |
| --- | --- | --- | --- | --- |
| Service selector changed to `app: missing` | Works | Fails | Fails | No ready endpoints for the Service; application pod remains healthy |
| `targetPort` changed from `http` to `9090` | Works | Fails | Fails | Ready pod exists; endpoint destination is wrong for the process |
| Access rule source changed to a different `/32` | Works | Works | Fails | Correct destination port but wrong source IP; do not use an address you don't control |
| Client VPN/public IPv4 changes | Works if API still reachable | Works if API still reachable | Fails | Source mismatch; API access may independently fail too |

The source-CIDR scenario is better reasoned through or demonstrated by a controlled network change; do not grant a stranger access just to make a fault. Never change an unrelated account security group.

## Senior follow-ups

- Why is `externalTrafficPolicy: Cluster` chosen? It permits forwarding to endpoints on other nodes; With `Local`, a node serves only local pods and can preserve the client's original IP address; `Cluster` can forward across nodes, adding another network hop. This arena has one node, so test multi-node claims elsewhere.
- Which observation separates a missing Service endpoint from a cloud firewall problem? Internal Service HTTP and the EndpointSlice contents.
- Why does a node replacement invalidate a bookmark? AWS can give the replacement node a different public IPv4 address. A production service needs a stable entry point, usually a load balancer and a domain name.
- Why avoid an ALB/NLB in this drill? It would add fixed-hour and usage charges plus controller/IAM complexity. Discuss those components in an interview; they are not provisioned here.
- What does Terraform state protect? It scopes managed identities. It does not make a broadly privileged AWS role safe, discover every permissive rule, or prove global cleanup.

Follow the README cleanup sequence even after a failed experiment. Do not leave the one-node arena running overnight.
