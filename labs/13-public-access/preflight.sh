#!/usr/bin/env bash
# Read-only identity and ownership checks. JSON on stdout; diagnostics on stderr.
set -euo pipefail
: "${AWS_PROFILE:?Export the AWS profile used for Game 07}"
: "${AWS_REGION:?Export AWS_REGION (normally us-west-2)}"
: "${TF_VAR_expected_account_id:?Export the expected 12-digit AWS account ID}"
: "${TF_VAR_lab_id:?Export the lab_id used to build Game 07}"
: "${CLUSTER_NAME:?Export the Game 07 cluster name}"
: "${LAB_KUBE_CONTEXT:?Export the Game 07 kubeconfig context}"
export AWS_PAGER=""
die() { printf 'Preflight stopped: %s\n' "$*" >&2; exit 1; }
for tool in aws kubectl jq curl python3; do command -v "$tool" >/dev/null || die "Missing $tool; run arcade setup."; done
[[ "$TF_VAR_expected_account_id" =~ ^[0-9]{12}$ ]] || die 'Invalid expected account ID.'
[[ "$CLUSTER_NAME" == "${TF_VAR_lab_id}-arcade" ]] || die 'Cluster must be the named Game 07 arena.'
aws_read() { aws --profile "$AWS_PROFILE" --region "$AWS_REGION" --cli-connect-timeout 5 --cli-read-timeout 15 --output json "$@"; }
identity="$(aws_read sts get-caller-identity)"
[[ "$(jq -r .Account <<<"$identity")" == "$TF_VAR_expected_account_id" ]] || die 'AWS account does not match expected_account_id.'
cluster="$(aws_read eks describe-cluster --name "$CLUSTER_NAME")"
jq -e --arg name "$CLUSTER_NAME" --arg id "$TF_VAR_lab_id" '
  .cluster | .name == $name and .status == "ACTIVE" and
  .tags.Project == "aws-interview-arcade" and .tags.Lab == "07" and .tags.LabId == $id
' <<<"$cluster" >/dev/null || die 'Cluster is not the active, tagged Game 07 arena.'
context="$(kubectl --context "$LAB_KUBE_CONTEXT" config view --minify -o json)"
[[ "$(jq -r '.clusters[0].cluster.server' <<<"$context")" == "$(jq -r '.cluster.endpoint' <<<"$cluster")" ]] || die 'Kubernetes context points at a different cluster.'
nodes="$(kubectl --context "$LAB_KUBE_CONTEXT" --request-timeout=15s get nodes -l role=lab -o json)"
jq -e '.items | length == 1 and (.[0] | .metadata.labels.role == "lab" and .metadata.labels["eks.amazonaws.com/nodegroup"] == "lab" and any(.status.conditions[]; .type == "Ready" and .status == "True"))' <<<"$nodes" >/dev/null || die 'This exercise requires exactly one Ready role=lab node in nodegroup lab.'
provider="$(jq -r '.items[0].spec.providerID' <<<"$nodes")"
[[ "$provider" =~ ^aws:///[a-z0-9-]+/(i-[0-9a-f]+)$ ]] || die 'Node providerID is not an EC2 instance.'
instance_id="${BASH_REMATCH[1]}"
instance="$(aws_read ec2 describe-instances --instance-ids "$instance_id")"
sg="$(jq -r '.cluster.resourcesVpcConfig.clusterSecurityGroupId' <<<"$cluster")"
vpc="$(jq -r '.cluster.resourcesVpcConfig.vpcId' <<<"$cluster")"
jq -e --arg id "$instance_id" --arg sg "$sg" --arg vpc "$vpc" --arg lab "$TF_VAR_lab_id" --arg cluster "$CLUSTER_NAME" '
  [.Reservations[].Instances[]] | length == 1 and (.[0] |
  .InstanceId == $id and .State.Name == "running" and .VpcId == $vpc and
  ((.PublicIpAddress // "") | length > 0) and any(.SecurityGroups[]; .GroupId == $sg) and
  ([.Tags[] | {key: .Key, value: .Value}] | from_entries |
   .Project == "aws-interview-arcade" and .Lab == "07" and .LabId == $lab and .Name == $cluster))
' <<<"$instance" >/dev/null || die 'Selected node must have a public IPv4, Game 07 tags, matching VPC, and the cluster security group.'
nodegroup="$(aws_read eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name lab)"
profile_arn="$(jq -r '.Reservations[0].Instances[0].IamInstanceProfile.Arn' <<<"$instance")"
[[ "$profile_arn" == "arn:aws:iam::${TF_VAR_expected_account_id}:instance-profile/"* ]] || die 'Node has no matching account instance profile.'
profile="$(aws_read iam get-instance-profile --instance-profile-name "${profile_arn##*/}")"
role="$(jq -r '.nodegroup.nodeRole' <<<"$nodegroup")"
[[ "$(jq -r '.nodegroup.status' <<<"$nodegroup")" == ACTIVE ]] || die 'Nodegroup is not ACTIVE.'
[[ "$role" == "arn:aws:iam::${TF_VAR_expected_account_id}:role/${CLUSTER_NAME}-node" ]] || die 'Nodegroup role does not match Game 07.'
jq -e --arg role "$role" '.InstanceProfile.Roles | length == 1 and .[0].Arn == $role' <<<"$profile" >/dev/null || die 'Node instance role does not match the Game 07 nodegroup role.'
source_ip="$(curl --noproxy '*' -4 -fsS --connect-timeout 5 --max-time 10 https://checkip.amazonaws.com)"
python3 - "$source_ip" <<'PY' || die 'Public source IP lookup did not return one IPv4 address.'
import ipaddress, sys
ipaddress.IPv4Address(sys.argv[1])
PY
jq -n --arg account "$TF_VAR_expected_account_id" --arg region "$AWS_REGION" --arg lab "$TF_VAR_lab_id" --arg profile "$AWS_PROFILE" \
  --arg cluster "$CLUSTER_NAME" --arg context "$LAB_KUBE_CONTEXT" \
  --arg node "$(jq -r '.items[0].metadata.name' <<<"$nodes")" \
  --arg id "$instance_id" --arg sg "$sg" \
  --arg public_ip "$(jq -r '.Reservations[0].Instances[0].PublicIpAddress' <<<"$instance")" \
  --arg cidr "$source_ip/32" \
  '{account: $account, region: $region, lab_id: $lab, aws_profile: $profile, cluster_name: $cluster, context: $context, node_name: $node, node_instance_id: $id, cluster_security_group_id: $sg, public_ip: $public_ip, allowed_cidr: $cidr}'
