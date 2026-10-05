# Game 11 — The incident gauntlet

You are the on-call platform engineer. Ten releases or operational requests fail in different ways. Recover each one, explain the evidence, and leave no workload behind. Expect 10–25 minutes per scenario. The cluster from [Game 07](../07-eks-foundation/README.md) is the only AWS infrastructure needed.

A namespace groups the exercise’s Kubernetes objects. Each scenario’s Terraform state records the objects it owns, so repairing or destroying one exercise does not mean managing the whole cluster.

Start with each scenario's README. Open HINTS.md one hint at a time; open ANSWERS.md only after forming a diagnosis. `starter/broken.yaml` is intentionally valid Kubernetes configuration with a runtime or operational fault. `solution/fixed.yaml` is a complete reference repair. The launcher copies the chosen candidate into a separate Terraform workload root, where the shared module owns the namespace, objects and diagnostic client. All configuration changes and cleanup go through Terraform. Read the diff after solving it.

| Scenario | Report from the team | Timebox |
|---|---|---:|
| [01](scenario-01/README.md) | The release never starts | 10 min |
| [02](scenario-02/README.md) | The replacement revision cannot initialize | 10 min |
| [03](scenario-03/README.md) | The process keeps disappearing | 10 min |
| [04](scenario-04/README.md) | The process runs but receives no Service traffic | 15 min |
| [05](scenario-05/README.md) | Capacity looks idle but the pod never starts | 10 min |
| [06](scenario-06/README.md) | The release inspection task fails | 15 min |
| [07](scenario-07/README.md) | Startup exits under a larger input | 15 min |
| [08](scenario-08/README.md) | Healthy replicas cannot undergo maintenance | 15 min |
| [09](scenario-09/README.md) | Green pods, broken Service traffic | 20 min |
| [10](scenario-10/README.md) | Accepted rollout never serves the new version | 25 min |

Start with a fresh, dedicated exercise namespace. If a create reports that an object already exists, inspect its owner and the original state before proceeding; never import unrelated shared-account resources just to make the exercise apply.

Use one scenario at a time. Each has its own `arcade-incident-NN` namespace. Small requests fit one t3.medium alongside the foundation add-ons; if other exercises consume capacity, clean those workloads first. Scenario 05 intentionally requests more than the lab can provide; do not add nodes to solve it. No scenario creates a load balancer, disk, or other AWS service. Cluster/worker billing continues while you work; reserve about $0.30 for two hours of the one-worker foundation, plus small transfer costs. Use the root cost guide's current assumptions.

Before the first incident:

```bash
: "${LAB_ROOT:?Set LAB_ROOT to the extracted kit directory}"
export LAB_KUBE_CONTEXT="${LAB_KUBE_CONTEXT:-arcade-lab}"
kubectl --context "$LAB_KUBE_CONTEXT" get nodes
kubectl --context "$LAB_KUBE_CONTEXT" get pods -A
```

The application image is a public Python image, and the Terraform-managed diagnostic client uses Alpine. Registry/network failures can obscure another intended fault: first check whether the selected image actually pulled. This kit was checked statically; these fixtures were not run in your AWS account.

For each incident, record: user-visible impact; pod phase and displayed status; the decisive event/log/condition; your hypothesis and what result would disprove it; the smallest correction; verification; prevention. `kubectl get pods` STATUS is a human display column and is not always the Pod API's `status.phase`. For example, a pod displaying CrashLoopBackOff can still have phase Running. Do not equate "Running" with healthy.

Evidence commands used repeatedly:

```bash
# Set NS using the selected scenario's README first.
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.metadata.creationTimestamp
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o jsonpath='{range .items[*]}{.metadata.name}{" phase="}{.status.phase}{"\n"}{end}'
```

Events are transient and messages can vary by version. Inspect container waiting/terminated states and conditions, not exact wording. Logs require a container to have started. `logs --previous` reads the previous terminated instance of the same container in the same pod, not an older Deployment revision. It can legitimately fail before a first restart; ordinary logs can also disappear after pod replacement.

Each incident awards 10 points: evidence 2, correct diagnosis 2, smallest safe fix 2, proof of recovery 2, explanation and cleanup 2. Ten attempted incidents give 100 possible points; for a subset, normalize as `points / (attempted incidents × 10) × 100`. A fix must be captured in the candidate and applied by Terraform. An imperative patch is incomplete even if traffic recovers. Reproduce the diagnosis without hints the next day using a fresh short session, then destroy the cluster again.

HTTP-serving exercises require a request through Service DNS from `arcade-diagnostics`, not just Ready pods or a local port-forward. This proves the internal path. [Game 13](../13-public-access/README.md) separately exercises a real public URL restricted to your workstation. Job and OOM exercises have API-result and process-stability checks instead of pretending every workload serves internet traffic.

Scenario 10 requires a healthy baseline followed by a broken update in the **same state**; do not skip its baseline. Scenario 08 uses one targeted eviction to test maintenance after the PDB is corrected through Terraform. That operation is the experiment, not an alternate repair path.

Cleanup each attempted scenario through its own state, even if its repair failed:

```bash
# Substitute the scenario you actually started. Do not create a new root for cleanup.
export INCIDENT=01
terraform -chdir="$LAB_ROOT/run/scenario-$INCIDENT" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-$INCIDENT" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-$INCIDENT" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-$INCIDENT" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "arcade-incident-$INCIDENT"
```

Require empty state and namespace `NotFound`. Permission and connection errors do not prove absence. Repeat only for the roots you actually created; keep their state until deletion is verified.

These namespaces contain no persistent storage or external load balancers. Workload Terraform destroy does not stop cluster billing. At session end, complete the teardown in Games 08–10 for any of their remaining workloads, then [destroy the Game 07 foundation](../07-eks-foundation/README.md). Do not remove finalizers blindly if deletion fails.

Official references: [debug running pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/), [pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), [probe behavior](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [resources](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/), [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/), [disruption budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/).
