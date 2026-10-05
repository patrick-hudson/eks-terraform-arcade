# Incident: healthy inside, unreachable outside

The application serves `arcade-public-ok` through its Kubernetes Service. Your laptop cannot reach it. Terraform manages both the workload and the one temporary ingress rule.

1. Run the ownership preflight. Explain how it ties the AWS account, EKS endpoint, Kubernetes node, EC2 instance, VPC, instance role and security group together.
2. Use Terraform to deploy this manifest through the shared Kubernetes exercise module, then apply the deliberately faulty access rule from this starter.
3. Capture the external connection failure. Compare process port, Service port, targetPort and nodePort. Prove the application and Service independently.
4. Repair source configuration, save and inspect a Terraform plan, then apply it. Keep the source restricted to your laptop's IPv4 `/32`; do not edit the EKS API allowlist to fix application traffic.
5. Prove the response body from the laptop through the public node IP. Explain why a successful port-forward would not prove this path.
6. Destroy the access rule while the workload still runs. Record the exact rule's absence and a failed NEW external connection, then destroy the workload through Terraform.
7. Before the session ends, destroy the Game 07 arena and verify its cleanup. An empty Game 13 state does not mean EKS billing stopped.

Stretch faults: change the Service selector, then its named targetPort, one at a time in candidate.yaml and apply with Terraform. Predict which layer checks fail before testing. Restore each through a reviewed Terraform plan.
