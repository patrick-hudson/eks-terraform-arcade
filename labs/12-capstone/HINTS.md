# Capstone hints

<details>
<summary>Hint 1 — A useful first minute</summary>

Confirm AWS account/region and the explicit Kubernetes context. Record what exists before creating anything. Read the working Game 07 outputs instead of guessing resource names. A connection or permission failure is not automatically an application failure.

</details>

<details>
<summary>Hint 2 — Build in dependency order</summary>

The foundation supplies the cluster and node; the application is Kubernetes configuration tracked in its own Terraform state; Pod Identity introduces an AWS/Kubernetes association; persistent volumes depend on the CSI driver and its identity. Keep their Terraform states distinct and follow Games 07–10. Do not point the Kubernetes provider at a cluster you are creating in the same operation just to shorten the command list.

</details>

<details>
<summary>Hint 3 — Choose evidence by failure stage</summary>

No scheduled node: examine scheduler events and requests. Container not created: inspect image/config dependencies. Repeated exits: inspect last termination and previous logs. Process alive without traffic: inspect readiness and endpoints. Denied AWS operation: compare workload identity and authorization boundaries. Denied Kubernetes API operation: inspect ServiceAccount, Role, binding, resource, and verb.

</details>

<details>
<summary>Hint 4 — Teardown is another dependency graph</summary>

Delete resources whose cleanup depends on a live Kubernetes controller first. A PVC may create an EBS volume outside the foundation's Terraform state; an Ingress or LoadBalancer Service can similarly create external resources. The provided core labs avoid load balancers, but do not assume that future extensions do. Wait for backing resources to disappear, then destroy the foundation. A failed deletion is an unfinished task, not a harmless warning.

</details>

<details>
<summary>Hint 5 — Keep one owner per release</summary>

Game 08 already owns `arcade-app`. Copy the capstone candidate into that same root, review its Terraform plan, and apply it. A second state for the same namespace creates competing owners. The rollback should update the Deployment and delete the tracked ConfigMap; a source-only edit without an apply is not a recovered release.

</details>
