# Scenario 06

The inspection task fails while trying to read its own namespace configuration. RBAC means role-based access control: a Role states allowed operations, and a RoleBinding grants them to an identity. Give it exactly the permission required and rerun it.

Budget: 10–15 minutes on the existing Game 07 cluster. No new AWS services. Terraform owns the namespace, workload, and diagnostic client. All repairs go through the working source and a reviewed Terraform plan; cleanup uses the same state. Do not change Kubernetes objects in the console or with imperative repair commands.

```bash
: "${LAB_ROOT:?Set LAB_ROOT first}"
: "${LAB_KUBE_CONTEXT:?Use the arcade-lab context from Game 07}"
export NS=arcade-incident-06
export SCENARIO_DIR="$LAB_ROOT/labs/11-incident-gauntlet/scenario-06"
export TF_VAR_aws_profile="${AWS_PROFILE:?Set the authenticated AWS profile}"
: "${TF_VAR_expected_account_id:?Set the intended AWS account ID}"
export TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
export TF_VAR_region="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
arcade start 11-06
cd "$LAB_ROOT/run/scenario-06"
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -w
```

Press Ctrl-C to stop the watch; it leaves the workload running. Expected observation: The Job reaches Failed. Its pod normally ends in phase Failed; logs describe an API request that did not succeed. Authentication, authorization, connectivity, and application errors are distinct possibilities.

Inspect task output after its pod starts (if the first log request says the pod is pending, inspect events and retry):

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get jobs,pods
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs job/inspect
```

Begin collecting evidence:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.metadata.creationTimestamp
```

Write down the first decisive fact before opening [HINTS.md](HINTS.md). Edit `candidate.yaml` in the prepared Terraform root. The module decodes that file into tracked Kubernetes resources; YAML is an input to Terraform, not a second deployment mechanism.

```bash
cd "$LAB_ROOT/run/scenario-06"
# Edit candidate.yaml and explain which observed failure your change addresses.
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
```

Terraform apply intentionally does not wait for workload readiness: a successful apply can create this broken exercise. Prove recovery with the checks in the answer, then run `terraform plan -detailed-exitcode`; exit 0 means no remaining configuration diff, 2 means changes remain, and 1 means an error.

A repair earns credit only when you demonstrate the expected function, explain why the observed failure followed from the configuration, and identify one prevention measure. The reference repair and verification commands are in [ANSWERS.md](ANSWERS.md).

Cleanup works before or after a repair:

```bash
terraform -chdir="$LAB_ROOT/run/scenario-06" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

The state listing should be empty and the namespace lookup should return NotFound. Any other error needs investigation. The cluster still bills: follow [Game 07 teardown](../../07-eks-foundation/README.md) when the session ends.

This Job talks to the private Kubernetes API rather than serving an HTTP endpoint. Its acceptance is a successful authorized API read plus an intentionally denied Secrets operation; public ingress would add no useful evidence.
