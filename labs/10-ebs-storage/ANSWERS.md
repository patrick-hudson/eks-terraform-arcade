# 10 · Answer

The fixture uses `ebs.csi.eks.amazonaws.com`, the EKS Auto Mode provisioner. This cluster uses the standard managed EBS CSI add-on, whose driver name is `ebs.csi.aws.com`. No installed controller services the fixture's request, so the PVC and Pod remain Pending. Expanding IAM permissions cannot correct that mismatch.

StorageClass provisioner is immutable: Kubernetes will not change it on an existing class. The module replaces the class through Terraform when its content changes. An unbound PVC can also retain old provisioner annotations, so this disposable fixture uses a two-stage repair. First remove the failed writer and claim through Terraform while keeping the namespace and class. Then create a new claim against the corrected class. **Never use this reset on a bound claim or valuable data.**

Prove the claim is unbound and check for a volume created before binding finished:

```bash
(
  set -euo pipefail
  EXISTING_PV="$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pvc data -o jsonpath='{.spec.volumeName}')"
  test -z "$EXISTING_PV" || { echo "STOP: claim is bound to $EXISTING_PV; preserve its data." >&2; exit 1; }
  REMAINING_VOLUMES="$(aws ec2 describe-volumes --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --filters Name=tag:Project,Values=aws-interview-arcade Name=tag:Lab,Values=10 \
    --query 'Volumes[].VolumeId' --output text)"
  test -z "$REMAINING_VOLUMES" || { echo "STOP: inspect existing lab-tagged volumes before resetting the claim." >&2; exit 1; }
  cd "$LAB_ROOT/run/10-ebs-storage/workload"
  cp candidate.yaml before-storage-repair.yaml
  # Temporary desired state: keep the namespace and corrected class, omit the failed consumer/claim.
  cat > candidate.yaml <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: arcade-storage
  labels:
    app.kubernetes.io/part-of: aws-interview-arcade
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: arcade-gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
  tagSpecification_1: "Project=aws-interview-arcade"
  tagSpecification_2: "Lab=10"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
YAML
  terraform plan -out=reset-unbound.tfplan
  terraform show reset-unbound.tfplan
  # Expect writer/PVC deletion and StorageClass replacement, preserving Namespace and diagnostics.
  terraform apply reset-unbound.tfplan
  cp "$LAB_ROOT/labs/10-ebs-storage/solution/workload.yaml" candidate.yaml
  terraform plan -out=repair.tfplan
  terraform show repair.tfplan
  # Expect a new writer and PVC against the corrected class.
  terraform apply repair.tfplan
)
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage rollout status deployment/writer --timeout=180s
```

Both stages are source changes applied by Terraform. The second plan creates the fresh claim, avoiding hidden annotations left on the first attempt. If it still remains Pending, inspect new PVC events and CSI logs; a different authorization or topology failure needs its own diagnosis.

Now run the mission's persistence check and capture the volume ID. The corrected class uses encrypted gp3, topology-aware delayed binding and `Delete`. A bound PV carries zone affinity; a Pod using it must run where it can attach. `ReadWriteOnce` means one node, not necessarily one Pod; it is not a substitute for application-level concurrency control.

The add-on's Pod Identity association targets `kube-system/ebs-csi-controller-sa`. Its IAM attachment resolves `AmazonEBSCSIDriverPolicyV2` by exact policy name. The current [IAM policy reference](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonEBSCSIDriverPolicyV2.html) and EKS tutorial show different ARN paths; looking up the policy avoids copying the stale path. The operator needs policy-read/list permissions, and this dedicated sandbox must not contain a customer policy with that same name. The controller needs permission not only to create and attach volumes but also to delete them, which is why teardown removes PVC/PV resources before the add-on/role and before the EKS cluster.

`strategy: Recreate` avoids a second writer overlapping during the one-replica rollout. A real stateful service still needs suitable workload controllers, backups, disruption policy, recovery tests and application consistency guarantees. Do not turn this single-writer exercise into a database availability claim.

Use the README Terraform replacement plan to recreate only `Deployment/writer` for the persistence test. Keep the claim and volume identity unchanged. Complete cleanup with the workload destroy and AWS volume-absence checks before destroying the add-on and role; an empty AWS root alone cannot certify that the dynamic disk is gone.
