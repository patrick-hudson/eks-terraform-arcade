#!/usr/bin/env bash
# Read-only inventory. A missing permission is an audit failure, not an empty result.
set -u
: "${AWS_REGION:?Export AWS_REGION}"
: "${TF_VAR_expected_account_id:?Export the intended account ID}"
: "${LAB_CLUSTER_NAME:?Capture LAB_CLUSTER_NAME before destroy}"
: "${LAB_VPC_ID:?Capture LAB_VPC_ID before destroy}"
actual=$(aws sts get-caller-identity --query Account --output text) || exit 1
if [[ "$actual" != "$TF_VAR_expected_account_id" ]]; then
  printf 'Wrong account: %s\n' "$actual" >&2
  exit 1
fi
failed=0
check() { "$@" || failed=1; }
printf '\nEKS clusters (your captured cluster should be absent):\n'
if clusters=$(aws eks list-clusters --region "$AWS_REGION" --query 'clusters[]' --output text); then
  printf '%s\n' "$clusters"
  # AWS cluster names contain no whitespace or glob characters.
  for cluster in $clusters; do
    if [[ "$cluster" == "$LAB_CLUSTER_NAME" ]]; then
      printf 'UNFINISHED: captured cluster %s still exists.\n' "$LAB_CLUSTER_NAME" >&2
      failed=1
    fi
  done
else
  failed=1
fi
printf '\nInstances in the former lab VPC (none running/pending/stopped):\n'
check aws ec2 describe-instances --region "$AWS_REGION" --filters "Name=vpc-id,Values=$LAB_VPC_ID" --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType]'
printf '\nLoad balancers in former VPC:\n'
check aws elbv2 describe-load-balancers --region "$AWS_REGION" --query "LoadBalancers[?VpcId=='${LAB_VPC_ID}'].[LoadBalancerArn,State.Code]"
printf '\nNAT gateways (no non-deleted lab gateways):\n'
check aws ec2 describe-nat-gateways --region "$AWS_REGION" --filter "Name=vpc-id,Values=$LAB_VPC_ID" --query 'NatGateways[].[NatGatewayId,State]'
printf '\nNetwork interfaces in former VPC:\n'
check aws ec2 describe-network-interfaces --region "$AWS_REGION" --filters "Name=vpc-id,Values=$LAB_VPC_ID" --query 'NetworkInterfaces[].[NetworkInterfaceId,Status,Description]'
printf '\nWider volume inventory: identify captured lab IDs and CSI tags:\n'
check aws ec2 describe-volumes --region "$AWS_REGION" --query 'Volumes[].[VolumeId,State,Size,Tags]'
printf '\nWider Elastic IP inventory:\n'
check aws ec2 describe-addresses --region "$AWS_REGION"
printf '\nWider owned snapshot inventory:\n'
check aws ec2 describe-snapshots --owner-ids self --region "$AWS_REGION" --query 'Snapshots[].[SnapshotId,VolumeId,StartTime,Tags]'
printf '\nLab-tagged resources (not comprehensive):\n'
check aws resourcegroupstaggingapi get-resources --region "$AWS_REGION" --tag-filters Key=Project,Values=aws-interview-arcade
printf '\nNamed-cluster presence and API failures affect the exit status. Inspect the other inventories and service-specific cleanup checks manually. No resources were deleted by this audit.\n'
exit "$failed"
