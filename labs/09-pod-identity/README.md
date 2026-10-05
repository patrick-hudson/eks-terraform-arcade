# 09 · Credentials without static keys

**Time box:** 30 minutes. **Difficulty:** mid–senior IAM/Kubernetes boundary debugging. **Depends on:** live lab 07 with a healthy Pod Identity agent. **Incremental AWS cost:** a tiny S3 fixture plus a handful of requests, normally pennies or less; existing EKS/node charges continue.

A Job is a task that runs to completion. This one should read exactly one S3 object using temporary workload credentials. Pod Identity maps its Kubernetes service account to an AWS IAM role; the association is the saved mapping between cluster, namespace and service-account name. The Job must print its assumed role and demonstrate that bucket listing is denied. The infrastructure deploys, but the supplied Job fails. Find the fault without adding credentials to Secrets, granting node-level S3 access or widening the object permission.

Your Terraform build must create a private encrypted bucket, one fixture object, an IAM role trusted by the EKS Pod Identity service, a scoped GetObject policy and one Pod Identity association. Keep this state separate from the cluster. The Kubernetes workload should use an AWS CLI version that supports Pod Identity.

## Build the AWS side and trigger the failure

```bash
: "${LAB_ROOT:?Complete docs/setup.md first}"
export LAB_KUBE_CONTEXT=arcade-lab
export TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
export AWS_REGION="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
export TF_VAR_region="$AWS_REGION"
export TF_VAR_aws_profile="${AWS_PROFILE:?Set the authenticated profile}"
: "${TF_VAR_expected_account_id:?Set the intended account ID}"
arcade start 09 --mode guided
cd "$LAB_ROOT/run/09-pod-identity"
# For the build challenge, use starter mode instead and author the AWS resources from the contract.
terraform init -lockfile=readonly
terraform validate
terraform plan -out=create.tfplan
terraform show create.tfplan
terraform apply create.tfplan
export FIXTURE_BUCKET="$(terraform output -raw bucket_name)"
# The Kubernetes state is separate and nested; the fixture contains no secret credentials.
cd "$LAB_ROOT/run/09-pod-identity/workload"
jq -n --arg bucket "$FIXTURE_BUCKET" --arg region "$AWS_REGION" \
  '{apiVersion:"v1",kind:"ConfigMap",metadata:{name:"fixture",namespace:"arcade-identity"},data:{bucket:$bucket,region:$region}}' > fixture.yaml
printf '%s\n' 'extra_manifest_paths = ["fixture.yaml"]' > fixture.auto.tfvars
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity wait --for=condition=failed job/reader --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity logs job/reader
```

The first Job failure is deliberate. Separate “no credentials” from “credentials with insufficient permission.” A Job is not a Deployment: once failed, changing its Pod template generally requires a fresh Job. The Terraform module tracks manifest content and plans that replacement automatically.

## Investigation toolbox

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity get pod -l job-name=reader -o yaml
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity get serviceaccounts
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system get pods -l app.kubernetes.io/name=eks-pod-identity-agent
aws eks list-pod-identity-associations --cluster-name "$TF_VAR_cluster_name" --region "$AWS_REGION"
terraform -chdir="$LAB_ROOT/run/09-pod-identity" output reader_role_arn
```

Compare the actual Pod, not only the local file, with the cloud association. Do not print temporary credential endpoints or copy credentials out of the Pod. The AWS CLI image uses the verified `:2.37.9` tag, which supports Pod Identity; record its resolved `status.containerStatuses[].imageID` for repeatable interview evidence.

Fix `run/09-pod-identity/workload/candidate.yaml` and let Terraform replace the Job:

```bash
cd "$LAB_ROOT/run/09-pod-identity/workload"
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity wait --for=condition=complete job/reader --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity logs job/reader
```

Pass: logs show the `...-arcade-reader` assumed role, `pod-identity-works`, an `AccessDenied` for listing the bucket, and the final `PASS` message. The Job only succeeds if the read works and the negative check contains AccessDenied. New IAM/association state can take a short time to propagate; if your configuration is correct but a transient authorization failure remains, wait briefly and rerun only the tracked Job with the following reviewed Terraform replacement plan. Do not remove the scoped policy to “fix” propagation.

```bash
cd "$LAB_ROOT/run/09-pod-identity/workload"
terraform plan -replace='module.exercise.kubernetes_manifest.job["Job/reader"]' -out=rerun.tfplan
terraform show rerun.tfplan
terraform apply rerun.tfplan
```

This lab tests workload-to-AWS API access, not public inbound HTTP. Keep its bucket private; making it public would bypass the authorization problem rather than solve it. Configuration repairs belong in Terraform or its manifest inputs, never console edits or direct Kubernetes writes.

Explain: What is the trust policy authorizing, and what is the permission policy authorizing? How is this different from IRSA? Why must an association match the actual workload identity? Why is disabling node metadata fallback useful in a diagnostic exercise? Which operator needs `iam:PassRole`?

## Cleanup, even if the Job is still failing

```bash
terraform -chdir="$LAB_ROOT/run/09-pod-identity/workload" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/09-pod-identity/workload" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/09-pod-identity/workload" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/09-pod-identity/workload" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace arcade-identity
# Continue only after NotFound and an empty workload state; other errors need investigation.
cd "$LAB_ROOT/run/09-pod-identity"
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
```

Pass: namespace absent, empty workload and AWS Terraform states. The dedicated fixture bucket permits deletion of its lab contents; never put valuable data in it. Keep this IAM role and association until its Pods are gone. Keep the cluster only while actively continuing, then run lab 07 teardown.

[Layered hints](HINTS.md) · [Exact repair](ANSWERS.md)

Sources: [Pod Identity associations and trust](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html), [agent setup](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-agent-setup.html), [AWS CLI container](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-docker.html).
