#!/usr/bin/env bash
set -euo pipefail
: "${LAB_ROOT:?Set LAB_ROOT to the package directory}"
: "${LAB_KUBE_CONTEXT:?Set LAB_KUBE_CONTEXT to the Game 07 context}"
: "${AWS_PROFILE:?Set the authenticated AWS profile used for this lab}"
: "${TF_VAR_expected_account_id:?Set the intended 12-digit account ID}"
[[ "$TF_VAR_expected_account_id" =~ ^[0-9]{12}$ ]] || { echo 'Invalid expected account ID.' >&2; exit 1; }
LAB10_RUN="$LAB_ROOT/run/10-ebs-storage"
LAB10_WORKLOAD="$LAB10_RUN/workload"
export TF_VAR_aws_profile="$AWS_PROFILE"
TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
TF_VAR_region="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
export TF_VAR_cluster_name TF_VAR_region
export AWS_REGION="$TF_VAR_region"
export AWS_DEFAULT_REGION="$TF_VAR_region"

# Diagnostic reads must address the same account and cluster as the Terraform provider.
ACTUAL_ACCOUNT="$(aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Account --output text)"
[[ "$ACTUAL_ACCOUNT" == "$TF_VAR_expected_account_id" ]] || { echo 'STOP: AWS account differs from expected_account_id.' >&2; exit 1; }
EXPECTED_ENDPOINT="$(aws eks describe-cluster --profile "$AWS_PROFILE" --region "$AWS_REGION" --name "$TF_VAR_cluster_name" --query cluster.endpoint --output text)"
CONTEXT_ENDPOINT="$(kubectl --context "$LAB_KUBE_CONTEXT" config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
[[ -n "$EXPECTED_ENDPOINT" && "$EXPECTED_ENDPOINT" == "$CONTEXT_ENDPOINT" ]] || { echo 'STOP: Kubernetes context points to another cluster.' >&2; exit 1; }

PV_NAME="$(kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-storage get pvc data --ignore-not-found -o jsonpath='{.spec.volumeName}')"
if [[ -n "$PV_NAME" ]]; then
  VOLUME_ID="$(kubectl --context "$LAB_KUBE_CONTEXT" get pv "$PV_NAME" -o jsonpath='{.spec.csi.volumeHandle}')"
  [[ "$VOLUME_ID" =~ ^vol-([0-9a-f]{8}|[0-9a-f]{17})$ ]] || { echo "Unexpected volume handle: $VOLUME_ID" >&2; exit 1; }
  printf '%s\n' "$VOLUME_ID" > "$LAB10_RUN/volume-id.txt"
fi

review_and_destroy() {
  local directory="$1" confirmation
  terraform -chdir="$directory" plan -destroy -out=destroy.tfplan
  terraform -chdir="$directory" show destroy.tfplan
  printf 'Review the destroy plan for %s. Type destroy to apply it: ' "$directory"
  read -r confirmation
  [[ "$confirmation" == destroy ]] || { echo 'Stopped; the saved plan has not been applied.' >&2; return 1; }
  terraform -chdir="$directory" apply destroy.tfplan
  local remaining_state
  remaining_state="$(terraform -chdir="$directory" state list)"
  [[ -z "$remaining_state" ]] || { printf 'STOP: Terraform state is not empty:\n%s\n' "$remaining_state" >&2; return 1; }
}

# Namespace, writer, PVC, StorageClass and diagnostic Pod share this workload state.
# Keep CSI and the node alive until the PVC's dynamically created AWS disk is absent.
review_and_destroy "$LAB10_WORKLOAD"
REMAINING_NAMESPACE="$(kubectl --context "$LAB_KUBE_CONTEXT" get namespace arcade-storage --ignore-not-found -o name)"
REMAINING_CLASS="$(kubectl --context "$LAB_KUBE_CONTEXT" get storageclass arcade-gp3 --ignore-not-found -o name)"
[[ -z "$REMAINING_NAMESPACE" && -z "$REMAINING_CLASS" ]] || { echo 'STOP: workload namespace or StorageClass still exists.' >&2; exit 1; }
if [[ -s "$LAB10_RUN/volume-id.txt" ]]; then
  VOLUME_ID="$(cat "$LAB10_RUN/volume-id.txt")"
  [[ "$VOLUME_ID" =~ ^vol-([0-9a-f]{8}|[0-9a-f]{17})$ ]] || { echo 'Invalid saved volume ID; inspect volume-id.txt.' >&2; exit 1; }
  echo "Waiting for AWS to delete $VOLUME_ID before removing CSI permissions."
  aws ec2 wait volume-deleted --profile "$AWS_PROFILE" --volume-ids "$VOLUME_ID" --region "$AWS_REGION"
fi
# Include volumes provisioned before a claim acquired a bound PV reference.
# Another session can match these tags: stop for inspection, never delete the inventory.
REMAINING_VOLUMES="$(aws ec2 describe-volumes --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --filters Name=tag:Project,Values=aws-interview-arcade Name=tag:Lab,Values=10 \
  --query 'Volumes[].VolumeId' --output text)"
if [[ -n "$REMAINING_VOLUMES" ]]; then
  echo "STOP: tagged lab 10 volumes still exist: $REMAINING_VOLUMES" >&2
  echo "Inspect their PVC/PV ownership before removing CSI; do not delete another session's volume." >&2
  exit 1
fi
review_and_destroy "$LAB10_RUN"
echo 'Game 10 workload and AWS states are empty; captured/tagged data volumes are absent. Game 07 still needs teardown.'
