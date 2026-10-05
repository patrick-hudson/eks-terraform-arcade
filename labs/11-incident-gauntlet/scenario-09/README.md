# Scenario 09

The release dashboard is green, and the application responds inside its pod. A caller using the application's normal Service address still fails. Restore that caller's request without changing the application image or adding AWS infrastructure.

Budget: 15–20 minutes on the existing Game 07 cluster. No new AWS services. The Service is deliberately **internal only**: successful in-cluster HTTP is the acceptance target here. [Game 13](../../13-public-access/README.md) adds the separate internet access exercise. A local port-forward would bypass part of this investigation and would not demonstrate public access.

Use Terraform for every infrastructure change. `kubectl` below only inspects resources or runs bounded diagnostic HTTP requests. Finish the previous exercise's Terraform teardown before starting this one.

Prepare the workspace from any directory:

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
arcade start 11-09
cd "$LAB_ROOT/run/scenario-09"
export NS=arcade-incident-09
export SCENARIO_DIR="$LAB_ROOT/labs/11-incident-gauntlet/scenario-09"
: "${LAB_KUBE_CONTEXT:?Use the Game 07 lab context}"
: "${TF_VAR_cluster_name:?Set this to the Game 07 cluster name}"
: "${TF_VAR_expected_account_id:?Set your sandbox account ID}"
: "${AWS_PROFILE:?Set the AWS profile for this lab}"
export TF_VAR_aws_profile="$AWS_PROFILE"
terraform init
terraform plan -out=incident.tfplan
terraform apply incident.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=condition=Ready pod/arcade-diagnostics --timeout=180s
```

Expect a healthy Deployment. First record what the application itself can serve:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment,pods,service
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec deployment/app -- \
  python -c 'from urllib.request import urlopen; print(urlopen("http://127.0.0.1:8080/", timeout=3).read().decode(), end="")'
POD_IP=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -l app=incident -o jsonpath='{.items[0].status.podIP}')
: "${POD_IP:?The application pod needs an IP before probing}"
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
  wget -T 3 -O - "http://$POD_IP:8080/"
```

Both requests should return `arcade-09-ok`. Now send the same request through the Service from the same diagnostic pod:

```bash
if kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
  wget -T 3 -O - http://app:8080/; then
  printf 'Service HTTP passed; check whether this workspace is already repaired.\n'
else
  printf 'Service HTTP failed. Preserve the error and identify the failing hop.\n'
fi
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get service app -o yaml
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get endpointslices -l kubernetes.io/service-name=app -o yaml
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get events --sort-by=.metadata.creationTimestamp
```

A timeout or refused connection is evidence; it is not a diagnosis by itself. An image pull, permission, or diagnostic-pod failure is a different setup problem. Do not infer a passing data path from readiness or EndpointSlices alone.

Write the first decisive observation before opening [HINTS.md](HINTS.md). Edit the workspace's `candidate.yaml`, review the exact Terraform changes, and apply the saved plan:

```bash
cd "$LAB_ROOT/run/scenario-09"
# Edit candidate.yaml in your editor.
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
```

Pass requires the **same diagnostic pod and same Service URL** to return `arcade-09-ok`, plus an explanation of why the earlier green health signals did not prove that result. [ANSWERS.md](ANSWERS.md) includes the reference repair, exact HTTP assertions, and production follow-up questions.

Always clean up through this workspace's Terraform state, before or after a repair:

```bash
cd "$LAB_ROOT/run/scenario-09"
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
terraform apply cleanup.tfplan
terraform state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

The final command should return NotFound; access errors are not cleanup proof. The EKS cluster still bills. Follow [Game 07 teardown](../../07-eks-foundation/README.md) at session end.
