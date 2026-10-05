# 07 · Reference answer

The complete answer is [`solution/main.tf`](solution/main.tf) plus [`solution/versions.tf`](solution/versions.tf). Copy them into `run/07-eks-foundation` and use the mission commands.

The two AZs satisfy control-plane network requirements; they do not make one worker highly available. The API public `/32` protects the control-plane entry point, while private endpoint access lets worker traffic stay inside the VPC. The cluster-generated security group is automatically associated with managed nodes because the launch template does not supply replacement security groups. There is no internet-facing node ingress rule.

The launch template deliberately controls disk lifecycle and CPU credit behavior. Standard credits may throttle sustained CPU work, which is a better lab tradeoff than unbounded surplus credit cost. Managed node updates can temporarily exceed desired capacity; do not perform upgrade experiments within a tight budget without reading the update behavior first.

`authentication_mode="API"` uses access entries. Disabling creator admin makes the admin dependency visible and reviewable. For an assumed CLI role, its IAM ARN must match the access entry. `update-kubeconfig` writes endpoint/authentication configuration; authorization still happens at the API server.

The node role has worker, image-pull and CNI permissions. The application in lab 09 receives a separate scoped role through Pod Identity. IMDSv2 with hop limit 1 limits ordinary pods' ability to reach instance credentials; it is not a complete boundary against privileged/host-network pods, so never grant them casually.

If the API times out, compare your current egress IP with the allowed `/32`. If it returns `Unauthorized`, inspect the CLI profile and access entry. If nodes fail to join, inspect node-group health, subnet routing/public IP configuration, cluster reachability and node IAM attachments; do not randomly open inbound ports.

Cost-sensitive choices are one small node, no NAT, no LB, no paid control-plane logging and no long retention. Production readiness would require different availability and observability choices. The fixture is a teaching system, not a production template.
