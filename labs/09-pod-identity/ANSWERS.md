# 09 · Answer

The failing Job uses `reader-old`, while the Pod Identity association targets `reader` in `arcade-identity`. Both Kubernetes service accounts exist, so scheduling succeeds, but the wrong Pod receives no Pod Identity credentials. `AWS_EC2_METADATA_DISABLED=true` prevents the AWS CLI from masking the mistake by attempting to use node metadata credentials.

The repair is `serviceAccountName: reader` in the Job. Do not annotate the service account with an IRSA role ARN: this exercise uses EKS Pod Identity, whose association is held by EKS. The trust permits `pods.eks.amazonaws.com` to call both `sts:AssumeRole` and `sts:TagSession`, restricted by the namespace and service-account session tags. The permission policy permits GetObject for one object ARN.

```bash
cd "$LAB_ROOT/run/09-pod-identity/workload"
cp "$LAB_ROOT/labs/09-pod-identity/solution/workload.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity wait --for=condition=complete job/reader --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-identity logs job/reader
```

The successful identity is an assumed session of the workload reader role, never the node role. A successful GetObject does not imply permission to ListBucket; those actions have different resource types. In this example the code intentionally allows only the object action, and the test proves the distinction.

Senior follow-up: the node's worker policy permits EKS Auth calls used by the agent; that does not give every Pod arbitrary application permissions. The Pod must have an association and the role must trust EKS Pod Identity. IRSA instead uses an OIDC provider and `AssumeRoleWithWebIdentity`. Both should avoid long-lived keys and both require an appropriate SDK credential chain.

The Job manifest hash changes when `serviceAccountName` changes, so the module replaces the immutable Job through Terraform. The namespace, fixture ConfigMap and service accounts remain tracked in the same workload state. If an unchanged failed Job needs another attempt after IAM propagation, use the README `-replace` command; do not remove it manually. A final no-change plan proves the repair is captured in source.
