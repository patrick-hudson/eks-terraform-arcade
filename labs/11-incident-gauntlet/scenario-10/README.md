# Scenario 10

A new release has been accepted, but users continue to receive the old response. Determine why the update makes no progress and release version 2 within the existing worker budget. Keep the declared application CPU request and replica count; do not add a worker.

Budget: 20–25 minutes on the existing Game 07 cluster. No new AWS services. This is an **internal HTTP release** exercise. [Game 13](../../13-public-access/README.md) covers the separate public endpoint. Port-forwarding does not prove internet access.

This incident needs the Game 07 shape: exactly one Ready `t3.medium` worker labelled `role=lab`. Clean up other exercise workloads through their own Terraform workspaces first. Never delete unrelated workloads or drain the node. The healthy baseline is a required checkpoint: applying the broken update to an empty namespace does not reproduce the incident.

Prepare the local workspace:

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
arcade start 11-10
cd "$LAB_ROOT/run/scenario-10"
export NS=arcade-incident-10
export SCENARIO_DIR="$LAB_ROOT/labs/11-incident-gauntlet/scenario-10"
: "${LAB_KUBE_CONTEXT:?Use the Game 07 lab context}"
: "${TF_VAR_cluster_name:?Set this to the Game 07 cluster name}"
: "${TF_VAR_expected_account_id:?Set your sandbox account ID}"
: "${AWS_PROFILE:?Set the AWS profile for this lab}"
export TF_VAR_aws_profile="$AWS_PROFILE"
```

Run this preflight before applying anything. It prints the node's allocatable resources, current workloads, and requested-resource totals. Check requests, not just live utilization. Stop if another exercise still consumes the node's capacity; use that exercise's Terraform destroy procedure and repeat the preflight.

```bash
(
  set -euo pipefail
  NODES=$(kubectl --context "$LAB_KUBE_CONTEXT" get nodes -o json)
  printf '%s' "$NODES" | jq -e '
    (.items | length) == 1 and
    .items[0].metadata.labels.role == "lab" and
    .items[0].metadata.labels["node.kubernetes.io/instance-type"] == "t3.medium" and
    (.items[0].spec.unschedulable // false | not) and
    any(.items[0].status.conditions[]; .type == "Ready" and .status == "True")
  ' >/dev/null
  CPU=$(printf '%s' "$NODES" | jq -r '.items[0].status.allocatable.cpu')
  printf '%s' "$CPU" | jq -e -R '
    (if endswith("m") then rtrimstr("m") | tonumber else tonumber * 1000 end)
    | . > 1000 and . < 2000
  ' >/dev/null
  NODE=$(printf '%s' "$NODES" | jq -r '.items[0].metadata.name')
  kubectl --context "$LAB_KUBE_CONTEXT" get pods -A -o wide
  kubectl --context "$LAB_KUBE_CONTEXT" describe node "$NODE"
  printf 'Preflight shape passed. Review the requested-resource totals before the baseline.\n'
)
```

If this check fails, the environment does not match the fixture. Do not compensate by adding workers or changing application requests. One application instance, the small diagnostic pod, and system workloads must fit; the baseline below confirms that experimentally.

Apply the healthy baseline through Terraform and require a real `arcade-10-v1` response:

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/scenario-10"
  cp "$SCENARIO_DIR/baseline/healthy.yaml" candidate.yaml
  terraform init
  terraform plan -out=baseline.tfplan
  terraform show baseline.tfplan
  terraform apply baseline.tfplan
  kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
  kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=condition=Ready pod/arcade-diagnostics --timeout=180s
  BODY=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
    wget -T 3 -O - http://app:8080/)
  test "$BODY" = arcade-10-v1
  printf 'BASELINE PASS: Service HTTP returned %s\n' "$BODY"
)
```

Do not proceed without `BASELINE PASS`. Keep this Terraform state. Now apply the update from the **same workspace**, after checking that the baseline still serves v1:

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/scenario-10"
  BODY=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
    wget -T 3 -O - http://app:8080/)
  test "$BODY" = arcade-10-v1
  cp "$SCENARIO_DIR/starter/broken.yaml" candidate.yaml
  terraform plan -out=release.tfplan
  terraform show release.tfplan
  terraform apply release.tfplan
  if kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=150s; then
    printf 'Unexpected successful rollout: re-check node count, requests, and baseline.\n'
  else
    printf 'Rollout failed to progress. Collect the Deployment and pending-pod evidence.\n'
  fi
)
```

Terraform accepting a manifest does not prove that its rollout completed. Preserve the failed rollout output instead of repeatedly applying it. Collect evidence and compare the version users still receive:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment,replicaset,pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe deployment app
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.metadata.creationTimestamp
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
  wget -T 3 -O - http://app:8080/
```

Your diagnosis must explain all three facts: the baseline served correctly, the new pod is not available, and the old response is still served. Write the decisive fact before reading [HINTS.md](HINTS.md). Edit `candidate.yaml`; use `terraform plan -out=repair.tfplan`, inspect the plan, then `terraform apply repair.tfplan`. The repair must keep one worker, one desired replica, and a 1000m application CPU request. State the availability tradeoff before applying it.

Pass requires a completed rollout and the **same Service URL** returning `arcade-10-v2`. A green pod count alone can refer to the old version. [ANSWERS.md](ANSWERS.md) includes the reference repair and HTTP assertion.

Cleanup works at baseline, during the stall, or after repair:

```bash
cd "$LAB_ROOT/run/scenario-10"
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
terraform apply cleanup.tfplan
terraform state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Expect empty state and NotFound for this namespace. Other errors need investigation. Retain the workspace until teardown succeeds. The cluster still bills; follow [Game 07 teardown](../../07-eks-foundation/README.md) at session end.
