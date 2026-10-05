# 10 · The disk that never appears

**Time box:** 30–40 minutes. **Difficulty:** mid–senior CSI/scheduling/storage operations. **Depends on:** live lab 07 and its Pod Identity agent. **Incremental cost:** one 1 GiB gp3 data volume, about $0.08 per month prorated at documented us-west-2 rates, plus the already running cluster/node. No snapshots or custom KMS key. Deleting the Pod alone does not stop volume charges.

Install the EBS CSI add-on (the Kubernetes driver that creates and attaches AWS disks) using Pod Identity, then deploy a one-replica writer with a 1 GiB claim. The supplied workload remains Pending. Diagnose whether it is a scheduling, identity, provisioning or attachment problem. Repair the infrastructure contract, prove the file survives Pod replacement, then verify AWS actually deleted the disk before removing its controller.

A PVC is a request for storage; the bound PV records the allocated volume. A StorageClass selects the disk driver and defaults.

Requirements: a gp3 StorageClass with encryption, `WaitForFirstConsumer`, reclaim policy `Delete`, a namespaced RWO (ReadWriteOnce: attached for writing from one node) claim and a small writer Deployment. Use `Recreate` rollout strategy for this one-node RWO example. Do not solve Pending by installing Auto Mode or creating another node.

## Install the controller

```bash
: "${LAB_ROOT:?Complete docs/setup.md first}"
export LAB_KUBE_CONTEXT="${LAB_KUBE_CONTEXT:-arcade-lab}"
export TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
export AWS_REGION="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
export TF_VAR_region="$AWS_REGION"
export TF_VAR_aws_profile="${AWS_PROFILE:?Set the authenticated profile}"
: "${TF_VAR_expected_account_id:?Set the intended account ID}"
arcade start 10 --mode guided
cd "$LAB_ROOT/run/10-ebs-storage"
# Use starter mode for the build challenge; author the IAM role, attachment and add-on first.
terraform init -lockfile=readonly
terraform validate
terraform plan -out=create.tfplan
terraform show create.tfplan
terraform apply create.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system rollout status deployment/ebs-csi-controller --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system rollout status daemonset/ebs-csi-node --timeout=180s
cd "$LAB_ROOT/run/10-ebs-storage/workload"
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage rollout status deployment/writer --timeout=90s
```

The first workload rollout timeout is intentional. The healthy controller does not imply that this particular PVC can bind. Terraform owns the Namespace, StorageClass, PVC, writer and diagnostic client in the nested workload state. You have no application data to preserve yet, but confirm that before allowing any claim replacement. All configuration fixes go through `candidate.yaml` or `.tf` files and a reviewed Terraform plan.

## Investigate and repair

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pods,pvc
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage describe pvc data
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage describe pods -l app=arcade-writer
kubectl --context "$LAB_KUBE_CONTEXT" get storageclass arcade-gp3 -o yaml
kubectl --context "$LAB_KUBE_CONTEXT" get csidrivers
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system logs deployment/ebs-csi-controller -c ebs-plugin --tail=50
```

Write your causal explanation before changing anything. Some StorageClass/PVC fields are immutable. The module plans StorageClass replacement when its contents change. Prove that this claim has no bound volume before applying the repair. The reference removes the failed writer/claim in one Terraform plan and recreates them in the next so stale driver annotations cannot survive; [hints](HINTS.md) and [answers](ANSWERS.md) include the exact source-and-plan workflow. Do not edit the StorageClass in the console or repair objects with kubectl.

## Prove binding and persistence after the repair

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage rollout status deployment/writer --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pvc data
export PV_NAME="$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pvc data -o jsonpath='{.spec.volumeName}')"
export VOLUME_ID="$(kubectl --context "$LAB_KUBE_CONTEXT" get pv "$PV_NAME" -o jsonpath='{.spec.csi.volumeHandle}')"
printf '%s\n' "$VOLUME_ID" > "$LAB_ROOT/run/10-ebs-storage/volume-id.txt"
aws ec2 describe-volumes --volume-ids "$VOLUME_ID" --region "$AWS_REGION" \
  --query 'Volumes[].{id:VolumeId,size:Size,type:VolumeType,encrypted:Encrypted,az:AvailabilityZone,state:State}'
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage exec deployment/writer -- cat /data/message
export ORIGINAL_POD_UID="$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pod -l app=arcade-writer -o jsonpath='{.items[0].metadata.uid}')"
terraform -chdir="$LAB_ROOT/run/10-ebs-storage/workload" plan \
  -replace='module.exercise.kubernetes_manifest.resource["Deployment/writer"]' -out=replace-writer.tfplan
terraform -chdir="$LAB_ROOT/run/10-ebs-storage/workload" show replace-writer.tfplan
# The plan must replace only the writer Deployment, leaving the PVC and StorageClass intact.
terraform -chdir="$LAB_ROOT/run/10-ebs-storage/workload" apply replace-writer.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage rollout status deployment/writer --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage exec deployment/writer -- cat /data/message
export REPLACEMENT_POD_UID="$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pod -l app=arcade-writer -o jsonpath='{.items[0].metadata.uid}')"
test "$ORIGINAL_POD_UID" != "$REPLACEMENT_POD_UID"
test "$PV_NAME" = "$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pvc data -o jsonpath='{.spec.volumeName}')"
```

Pass: PVC `Bound`; AWS shows 1 GiB encrypted gp3; the Pod UID changes, the PVC still references the same PV, and the replacement Pod reads `survived-pod-replacement`. The writer creates this marker only when `/data/message` is absent; combine the content check with unchanged PV identity rather than treating the marker alone as persistence proof. `WaitForFirstConsumer` makes binding topology aware: no consumer can mean an intentionally Pending PVC. This exercise has a consumer, so inspect why it still cannot bind. The PVC and Deployment are in Terraform state. The dynamic PV and EBS disk are created by Kubernetes/CSI and are not directly managed by this state; their deletion must be verified separately. This storage lab has no internet-facing service because its acceptance is persistence, attachment and cleanup.

Explain: Why does EBS topology affect scheduling? Why is a node replacement different from a Pod replacement? What does RWO guarantee, and what does it not guarantee? How do `Retain`, `Delete`, finalizers and controller permissions affect cleanup? Why can deleting the cluster before the PVC leak a billable volume?

## Cleanup, healthy or broken

Use the supplied script. It captures any bound volume ID, destroys the workload Terraform root, including its claim, while the controller is alive, waits for AWS volume deletion, and only then presents the Terraform destroy plan for the add-on and IAM role. It shows each saved destroy plan and asks you to type `destroy` before applying it. It stops on errors so it cannot silently advance past a leaked volume. Read-only account and cluster checks also catch the wrong profile or Kubernetes context before deletion. It does not tear down lab 07.

```bash
bash "$LAB_ROOT/labs/10-ebs-storage/cleanup.sh"
```

Pass: namespace and StorageClass absent; captured data volume returns `InvalidVolume.NotFound`; both this lab's workload and AWS Terraform states empty. If storage provisioning ever created a volume but the claim did not bind, inspect tagged EBS volumes in the root cleanup audit before deleting the controller. Do not strip finalizers as a shortcut. Keep the cluster only while actively continuing, then run lab 07 teardown.

[Layered hints](HINTS.md) · [Exact repair](ANSWERS.md)

Sources: [EKS EBS CSI](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html), [StorageClasses](https://kubernetes.io/docs/concepts/storage/storage-classes/), [persistent volume lifecycle](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).
