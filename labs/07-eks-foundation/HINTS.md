# 07 · Layered hints

Open one hint at a time.

<details><summary>Hint 1 — Draw the paths in words</summary>

Your laptop reaches the public API endpoint from one `/32`. Nodes use the private endpoint inside the VPC. Nodes reach image registries and AWS APIs through an internet gateway and their public IPv4 addresses. A route by itself does not give a node a public address.
</details>

<details><summary>Hint 2 — Identity has separate planes</summary>

The cluster service role, EC2 node role, human access entry and Kubernetes workload role are distinct. `aws sts get-caller-identity` may return an STS session ARN; the EKS access entry requires the permanent IAM role ARN.
</details>

<details><summary>Hint 3 — Order matters</summary>

VPC CNI must exist before nodes can become healthy. Start with self-managed core add-ons, then adopt them with managed add-ons using overwrite after the node group joins. IAM policy attachments must remain until their dependents are destroyed.
</details>
