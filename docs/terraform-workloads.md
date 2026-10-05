# Repair Kubernetes through Terraform

The source of truth for a Kubernetes exercise is `candidate.yaml` in its prepared workload directory. Terraform reads that file, owns its resources in a separate state, and plans every repair. Editing YAML is a Terraform configuration change because the module passes its decoded contents to `kubernetes_manifest`. No AWS Console edits, `kubectl apply`, `kubectl patch`, `kubectl edit`, or imperative rollout changes are needed.

`kubectl get`, `describe`, `logs`, `wait`, `rollout status`, `auth can-i`, and a read-only HTTP request through `exec` provide evidence. These diagnostic commands do not replace the Terraform repair.

## Prepare and select the cluster

Complete Game 07 first. Kubernetes planning needs a reachable, authenticated API server to discover schemas. A local `terraform validate` proves configuration syntax/provider compatibility, not that a manifest will be admitted or a Pod will start. This requirement is documented by the [Kubernetes provider](https://registry.terraform.io/providers/hashicorp/kubernetes/3.3.0/docs/resources/manifest).

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
: "${AWS_PROFILE:?Set the named AWS profile you authenticated with}"
: "${TF_VAR_expected_account_id:?Set the intended 12-digit account ID}"
: "${CLUSTER_NAME:?Use the Game 07 cluster name}"
export AWS_REGION=us-west-2
export TF_VAR_region="$AWS_REGION"
export TF_VAR_aws_profile="$AWS_PROFILE"
export TF_VAR_cluster_name="$CLUSTER_NAME"

arcade start 11-01
cd "$LAB_ROOT/run/scenario-01"
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
```

The AWS provider checks `expected_account_id`. The Kubernetes provider reads the specified EKS endpoint and certificate from AWS and obtains a token with the explicit AWS profile, region, and cluster name. It does not load the current kubeconfig or execute its authentication plugins. Keep using the Game 07 `LAB_KUBE_CONTEXT` for diagnostic commands, and confirm that it names this same cluster.

The launcher copies the portable Terraform root, its dependency lock, the workload module, and the selected YAML. It does not apply anything. Resume an existing workspace instead of preparing another state for the same namespace. Two states must never own the same Kubernetes object.

## Reproduce, repair, prove

An apply can succeed while the application is broken. The module deliberately does not wait for Deployment readiness or Job success: an image pull failure, missing ConfigMap, or pending Pod is often the starting condition.

```bash
export NS=$(terraform output -raw namespace)
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.lastTimestamp

# Record the symptom and hypothesis, then repair the authored configuration.
${EDITOR:-vi} candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan

# Follow this incident's specific behavioral proof as well as checking drift.
terraform plan -detailed-exitcode
```

A final plan exit code of **0** means no Terraform changes, **2** means changes remain, and **1** means a planning error. A clean plan alone does not prove that HTTP traffic or authorization works; execute the lab's assertions and inspect their results.

Ordinary resources have stable addresses such as `module.exercise.kubernetes_manifest.resource["Deployment/app"]`. Reordering documents changes neither their names nor their Terraform identities. The module creates the namespace first, then StorageClasses and ordinary resources, then Jobs and authored Pods. This ensures that a Job's ServiceAccount and fixture ConfigMap exist before it starts.

## HTTP evidence from a Terraform-managed client

Each workload root can create a small `arcade-diagnostics` Pod in its own namespace. It uses Alpine, runs as a non-root user with a read-only filesystem and no service-account token, and restarts its sleeping process to remain available during practice. It consumes the existing cluster's node allocation; it does not create a load balancer or a new node.

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait \
  --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
  wget -q -T 3 -O - http://app:8080/
```

Use the Service name, port, and expected body defined by the incident. `exec` here runs a bounded read-only request in the already Terraform-managed client. It does not create a test Pod. Set `TF_VAR_create_diagnostic_pod=false` before planning when the helper is unnecessary. Terraform removes it on the next reviewed apply.

A ClusterIP response proves in-cluster access. A port-forward proves a path through the API server. Neither proves public internet reachability. Game 13 adds an explicit, bounded public-path exercise; follow its public address, security-group, and real HTTP checks instead of treating `kubectl get pods` as internet proof.

## Immutable Jobs, Pods, and StorageClasses

A Job's Pod template cannot be patched in place. The module hashes its authored manifest and plans a **destroy/create replacement** whenever it changes. Authored standalone Pods and StorageClasses have the same explicit replacement mechanism. Review the replacement in the saved Terraform plan before applying it.

To rerun an unchanged completed Job, request a Terraform replacement:

```bash
terraform plan \
  -replace='module.exercise.kubernetes_manifest.job["Job/reader"]' \
  -out=rerun.tfplan
terraform show rerun.tfplan
terraform apply rerun.tfplan
```

This replaces only that named Job. There is no imperative delete step. Changing a StorageClass does not rewrite a bound PV's driver or migrate existing data; follow Game 10's evidence and teardown order. Never remove PVC finalizers to make cleanup look complete.

## Separate AWS and workload states

Games 09 and 10 retain their AWS configuration in `run/09-pod-identity` and `run/10-ebs-storage`. Their Kubernetes roots are the nested `workload/` directories. Apply the AWS prerequisites first, then enter the workload directory for its own init/plan/apply sequence. Capstone updates the existing Game 08 workload state rather than creating a second owner for `arcade-app`.

Game 09 also needs a non-secret fixture ConfigMap containing the generated bucket name and region. Write that YAML into `workload/fixture.yaml`, then include it with `extra_manifest_paths = ["fixture.yaml"]` in a local `.tfvars` file. Terraform owns the ConfigMap alongside the Job. The bucket value is an identifier, not an AWS credential. Never put credentials or Secrets into these manifests or commit local state.

The module permits exactly one `arcade-*` namespace, keeps namespaced objects inside it, and allows only the curriculum's resource kinds. It excludes Secrets and cluster-wide RBAC. The only supported cluster-scoped object is an `arcade-*` StorageClass. These checks constrain accidental scope; they are not an IAM boundary or a substitute for reviewing a plan.

## Destroy in dependency order

Keep the EKS API reachable until every workload state has been destroyed. From the particular workload directory:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
# Expected: empty Terraform state and Kubernetes NotFound.
```

A non-empty state, access error, or namespace stuck Terminating is unfinished cleanup. Preserve the directory and investigate. For Game 10, also confirm the managed StorageClass, PV, and EBS volume are gone before destroying the CSI add-on. Destroy the supporting AWS state next, and destroy Game 07 last. Deleting a namespace does not stop the EKS or EC2 clock.

## Local verification without a cluster

The tests parse the authored YAML and plan resources through Terraform's mocked Kubernetes provider. They check namespace ownership, stable resource keys, scalar preservation, optional diagnostics, all existing curriculum manifests, and immutable-resource replacements. They do not prove Kubernetes admission, scheduling, network reachability, or live AWS cleanup.

```bash
cd "$LAB_ROOT"
terraform -chdir=modules/kubernetes-exercise init -backend=false -lockfile=readonly
terraform -chdir=modules/kubernetes-exercise validate
report=$(mktemp)
terraform -chdir=modules/kubernetes-exercise test -json -verbose > "$report"
python3 modules/kubernetes-exercise/tests/assert-replacements.py "$report"
rm "$report"
```

The YAML parser preserves document-adjacent trailing newlines in block scalars. This matters for embedded ConfigMap content: the provider's `manifest_decode_multi` function in 3.3.0 removed that newline in a focused local test, so this module splits only column-zero document separator lines and uses Terraform's `yamldecode` for each complete document.
