# Answer — scenario 10

**The rollout requires temporary capacity that this one-node environment cannot provide.** The old pod requests 1000m CPU. `maxSurge: 1` and `maxUnavailable: 0` create a second 1000m pod while requiring the old one to stay available. The worker has less than 2000m allocatable CPU after reservations, with additional system requests. The scheduler cannot place the new pod, and the Deployment cannot remove the old pod first. The server image is healthy; the new process has not started.

The two manifest revisions differ in their release marker and pod-template annotation. An actual `arcade-10-v1` response establishes the healthy baseline; the later response staying at v1 explains why “one Ready pod” is insufficient release proof. A progress deadline reports the stall; it does not supply capacity or repair the rollout. Read the [Kubernetes Deployment strategy documentation](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy).

For this constrained lab, accept a brief outage: set `maxSurge: 0` and `maxUnavailable: 1`. The reference keeps the 1000m request, one desired replica, the same image, and the same worker. Apply the repair through the existing Terraform workspace:

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/scenario-10"
  cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
  terraform plan -out=repair.tfplan
  terraform show repair.tfplan
  terraform apply repair.tfplan
  kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
  BODY=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
    wget -T 3 -O - http://app:8080/)
  test "$BODY" = arcade-10-v2
  printf 'PASS: completed rollout serves %s through the Service\n' "$BODY"
  kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment,replicaset,pods -o wide
  terraform plan -detailed-exitcode
)
```

Pass: one v2 application replica is Ready, the rollout completes, the Service returns `arcade-10-v2`, and Terraform's final plan exits 0. Exit 2 means remaining changes; exit 1 means an error. A completed rollout plus the versioned HTTP result is the check; the static YAML alone is not proof.

There can be a short interval with no ready application endpoint as the old pod exits and v2 starts. The allowed unavailability is a conscious lab constraint. A PodDisruptionBudget does not redefine the Deployment's rolling-update strategy, and increasing rollout timeouts cannot fix insufficient requested capacity. Deleting the old pod imperatively bypasses the intended infrastructure change and may simply replace it with another old replica.

For a production design, discuss pre-provisioned or autoscaled capacity, minimum replica count, measured resource requests, rollout surge budget, readiness, and error-budget tolerance. An autoscaler needs permissions, quotas, instance availability, and a bounded provisioning time; its presence alone does not guarantee a safe rollout. Do not casually lower requests until the arithmetic fits without evidence that the application can meet its SLO at that allocation. This exercise deliberately does not create additional workers.

Counterfactuals matter: an `ImagePullBackOff` would implicate image access; a scheduled pod repeatedly restarting would shift attention to process/configuration; a pod waiting on a PVC or an incompatible node selector would require different evidence. Here, the decisive evidence is an unscheduled v2 pod with insufficient CPU, combined with the old replica and the strategy's required overlap.

Keep the public-access claim separate: this Service is ClusterIP. The HTTP probe proves an internal caller can receive the intended version, not internet reachability. [Game 13](../../13-public-access/README.md) covers the public route and its access controls.

Tear down the workload from its owning state:

```bash
cd "$LAB_ROOT/run/scenario-10"
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
terraform apply cleanup.tfplan
terraform state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

The named namespace should be NotFound and the workload state empty. Destroy Game 07 at the end of the session; workload teardown does not stop EKS billing.
