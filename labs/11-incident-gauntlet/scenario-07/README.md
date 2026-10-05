# Scenario 07

The service began exiting during startup after an input grew. Restore it within the existing memory budget.

Budget: 10–15 minutes on the existing Game 07 cluster. No new AWS services. Terraform owns the namespace, workload, and diagnostic client. All repairs go through the working source and a reviewed Terraform plan; cleanup uses the same state. Do not change Kubernetes objects in the console or with imperative repair commands.

```bash
: "${LAB_ROOT:?Set LAB_ROOT first}"
: "${LAB_KUBE_CONTEXT:?Use the arcade-lab context from Game 07}"
export NS=arcade-incident-07
export SCENARIO_DIR="$LAB_ROOT/labs/11-incident-gauntlet/scenario-07"
export TF_VAR_aws_profile="${AWS_PROFILE:?Set the authenticated AWS profile}"
: "${TF_VAR_expected_account_id:?Set the intended AWS account ID}"
export TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
export TF_VAR_region="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
arcade start 11-07
cd "$LAB_ROOT/run/scenario-07"
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -w
```

Press Ctrl-C to stop the watch; it leaves the workload running. Expected observation: The container restarts or reaches CrashLoopBackOff. Capture the terminated reason and exit code before changing anything; exit code alone is not enough to identify why it stopped.

Inspect the stalled rollout with a bounded wait. A timeout is expected for the broken release; continue investigating.

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=45s
```

Begin collecting evidence:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.metadata.creationTimestamp
```

Write down the first decisive fact before opening [HINTS.md](HINTS.md). Edit `candidate.yaml` in the prepared Terraform root. The module decodes that file into tracked Kubernetes resources; YAML is an input to Terraform, not a second deployment mechanism.

```bash
cd "$LAB_ROOT/run/scenario-07"
# Edit candidate.yaml and explain which observed failure your change addresses.
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
```

Terraform apply intentionally does not wait for workload readiness: a successful apply can create this broken exercise. Prove recovery with the checks in the answer, then run `terraform plan -detailed-exitcode`; exit 0 means no remaining configuration diff, 2 means changes remain, and 1 means an error.

A repair earns credit only when you demonstrate the expected function, explain why the observed failure followed from the configuration, and identify one prevention measure. The reference repair and verification commands are in [ANSWERS.md](ANSWERS.md).

Cleanup works before or after a repair:

```bash
terraform -chdir="$LAB_ROOT/run/scenario-07" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

The state listing should be empty and the namespace lookup should return NotFound. Any other error needs investigation. The cluster still bills: follow [Game 07 teardown](../../07-eks-foundation/README.md) when the session ends.

This memory exercise runs a bounded background process, not a web server. Its acceptance is the allocation log and stable restart count. Do not add a public endpoint to diagnose an OOM.
