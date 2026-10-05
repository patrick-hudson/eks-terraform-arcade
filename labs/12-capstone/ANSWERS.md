# Capstone reference approach

There is no single monolithic apply command. The reference implementation is the set of existing solutions and commands in [Game 07](../07-eks-foundation/README.md), [Game 08](../08-kubernetes-release/README.md), [Game 09](../09-pod-identity/README.md), and [Game 10](../10-ebs-storage/README.md). Use them in that order, then run the selected [Game 11](../11-incident-gauntlet/README.md) incident. Do not create an additional EKS cluster for this capstone.

A passing demonstration has evidence for every boundary:

- **Terraform:** separate states match actual infrastructure; a reviewed plan shows only intended changes. Provider credentials are external to source and state is treated as sensitive. Explain state locking, drift, imports, refactors using moved blocks, and why removing a state address is not deletion.
- **Network:** the lab's public worker connectivity avoids a NAT charge and enables image pulls; the API endpoint remains explicitly controlled. Security groups are stateful. A public subnet route does not alone give an instance a public address. Explain DNS resolution and how you would diagnose failed registry access.
- **Application:** the rollout becomes ready and a request returns the expected content. Explain readiness versus liveness, requests versus limits, Deployment strategy, and why a second replica on the same node is not node-level fault tolerance.
- **Identity:** an allowed AWS request succeeds and a denied request fails for the intended permission reason. Explain authentication versus authorization and why the node role should not carry every application's permissions. A Kubernetes RoleBinding does not grant S3 access; Pod Identity does not itself grant Kubernetes API access.
- **Storage:** a marker survives pod replacement while the PVC remains. Explain RWO's node-level meaning, availability-zone binding, and Delete versus Retain. Persistence is not a backup or a disaster-recovery strategy.
- **Incident:** show one decisive event, log, or condition; formulate a hypothesis that predicts it; fix the actual source field; verify the intended function. Do not claim victory merely because the pod's phase is Running.
- **Change:** a minimal configuration edit causes the expected new application behavior and a controlled rollout. Restoring the known-good candidate and applying its reviewed Terraform plan restores the previous behavior and removes tracked objects omitted from that source. Explain what should happen if only the ConfigMap changes and the application consumes it through environment variables.
- **Cleanup:** Kubernetes-created external resources disappear while their controllers still work. Terraform destroy completes in the correct roots, resource inventory is checked, and billing is checked later for lag. State files survive long enough to retry incomplete teardown.

Useful namespace-specific evidence commands after the individual games are applied:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app get deployments,pods,services,endpointslices
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity get pods,serviceaccounts
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pods,pvc
kubectl --context "$LAB_KUBE_CONTEXT" get pv
```

These inspect the expected namespace contract only; use each game's README for object-specific exec, rollout, and teardown commands. Read broad inventory commands; delete only known lab-owned resources.

A strong senior answer also names what would change in production: separate accounts, stronger network isolation, multiple failure domains, immutable artifacts, secrets handling, upgrade testing, policy checks, workload-specific identities, backup/restore verification, and budget ownership. State a concrete reason for each change and its cost/operational tradeoff. Simply naming tools earns little credit.

Score using SCORECARD.md. If a service is still running after the interview, finish teardown before treating the exercise as complete. A successful local YAML parse or Terraform validate is not proof that a cloud apply, IAM authorization, CSI provisioning, or destroy will succeed in a particular account. This kit was not deployed into your account during preparation.


## Concrete response change and rollback

Complete Game 08 first. Its Terraform root already owns `arcade-app`; this capstone reuses that root and state. Never apply the same namespace from another Terraform root. `solution/workload-v2.yaml` adds a ConfigMap and changes the Pod template, so Terraform updates the existing release and starts a rollout.

```bash
cd "$LAB_ROOT/run/08-kubernetes-release"
cp "$LAB_ROOT/labs/12-capstone/solution/workload-v2.yaml" candidate.yaml
terraform plan -out=release-v2.tfplan
terraform show release-v2.tfplan
terraform apply release-v2.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app rollout status deployment/web --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app wait --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app exec arcade-diagnostics -- \
  sh -ec 'wget -T 10 -qO- http://web.arcade-app.svc.cluster.local | grep arcade-release-v2'
terraform plan -detailed-exitcode
```

Pass: the Service response includes `arcade-release-v2` and the final plan exits 0. This proves in-cluster traffic and captured configuration; an internet URL is tested separately in Game 13.

Restore the original source through the same Terraform state:

```bash
cd "$LAB_ROOT/run/08-kubernetes-release"
cp "$LAB_ROOT/labs/08-kubernetes-release/solution/workload.yaml" candidate.yaml
terraform plan -out=rollback.tfplan
terraform show rollback.tfplan
# Expect the Deployment to revert and the tracked web-content ConfigMap to be destroyed.
terraform apply rollback.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app rollout status deployment/web --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app exec arcade-diagnostics -- \
  sh -ec 'wget -T 10 -qO- http://web.arcade-app.svc.cluster.local | grep "Welcome to nginx"'
terraform plan -detailed-exitcode
```

Terraform tracks the ConfigMap, so removing it from the manifest removes its resource from configuration and plans deletion. A bare Kubernetes manifest apply does not provide this pruning contract. A ConfigMap data edit by itself also does not change the Deployment Pod-template hash; the v2 annotation makes rollout explicit. Versioning configuration alongside releases is part of the production answer.

Finish the Game 08 Terraform destroy sequence after the rollback demonstration, then the other games' ordered cleanup. No direct Kubernetes configuration writes or AWS console repairs are part of this capstone.
