# 07 · Build the short-lived EKS arena

**Time box:** 45–60 minutes including provisioning. **Difficulty:** mid–senior platform design. **Depends on:** root setup, AWS credentials and `kubectl`. **Cost:** roughly $0.15–$0.20 per hour for the whole one-node arena at the documented us-west-2 rates; reserve $0.25/hour. Creation and deletion time count. Reuse it for 08–12 in one session, then destroy it. See [the cost guide](../../docs/cost-and-cleanup.md).

You have an AWS account, possibly with existing resources, and must build a separate disposable Kubernetes platform without a NAT gateway, load balancer, SSH key or accidental admin identity. Explain how traffic reaches the cluster and which identities may use it before applying. Review the plan for new lab resources only; existing account resources are not part of this exercise.

Your build must have:

- Two `/24` public subnets in separate supported availability zones, an internet gateway and explicit routes.
- An EKS 1.36 control plane with standard support, private API connectivity for nodes, and public API access restricted to your current IPv4 `/32`.
- API access entries and an explicit permanent IAM administrator principal. Disable implicit cluster-creator admin.
- One managed AL2023 `t3.medium` node, 20 GiB encrypted gp3 root disk, deletion on termination, required IMDSv2 and hop limit 1. Use standard T3 credits to avoid surplus-credit charges. Maximum group size is two; no autoscaler is installed.
- Managed VPC CNI, kube-proxy, CoreDNS and Pod Identity agent add-ons. Bootstrap networking before the node; adopt it after the node joins.
- Outputs `cluster_name`, `region`, `vpc_id`, `node_role_arn`, `cluster_security_group_id`; node label `role=lab`.

Public subnets are a deliberate cost tradeoff for this isolated exercise. The node has no public inbound rule or SSH access. A production answer should discuss private nodes, endpoint design, egress controls, multiple nodes/AZs, availability, control-plane logs, patching and cost. The node IAM role includes CNI permissions here; discuss moving them to the CNI service account in a hardened platform.

## Build and apply

First complete [setup](../../docs/setup.md). Use the IAM role/user ARN behind your AWS CLI session for `TF_VAR_admin_principal_arn`; an STS `assumed-role` ARN is invalid. For IAM Identity Center, use the permanent IAM role ARN including its path, and keep that CLI profile active. The package is for the standard `aws` partition.

```bash
: "${LAB_ROOT:?Complete docs/setup.md first}"
export LAB_KUBE_CONTEXT="${LAB_KUBE_CONTEXT:-arcade-lab}"
# Set these real values; never copy an example account or IP.
: "${TF_VAR_admin_principal_arn:?Export your permanent IAM role/user ARN from setup}"
export TF_VAR_allowed_cidr="$(curl -fsS https://checkip.amazonaws.com)/32"
: "${TF_VAR_expected_account_id:?Complete docs/setup.md}"
: "${TF_VAR_region:=us-west-2}"
export TF_VAR_region
mkdir -p "$LAB_ROOT/run/07-eks-foundation"
cd "$LAB_ROOT/run/07-eks-foundation"
```

Write `versions.tf` and `main.tf` against the contract above. For the guided path, seed the complete working example:

```bash
cp "$LAB_ROOT/labs/07-eks-foundation/solution/"*.tf .
cp "$LAB_ROOT/labs/07-eks-foundation/solution/.terraform.lock.hcl" .
terraform init
terraform fmt -check
terraform validate
terraform plan -out=create.tfplan
terraform show create.tfplan
# Check the account, region, /32, instance type, node count and absence of NAT/LB.
terraform apply create.tfplan
export CLUSTER_NAME="$(terraform output -raw cluster_name)"
export AWS_REGION="$(terraform output -raw region)"
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION" --alias "$LAB_KUBE_CONTEXT"
kubectl --context "$LAB_KUBE_CONTEXT" wait --for=condition=Ready nodes --all --timeout=300s
kubectl --context "$LAB_KUBE_CONTEXT" get nodes -L role -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system get pods
```

Keep the terminal environment and Terraform state. A dedicated access entry authenticates the IAM principal, then the EKS access policy authorizes it; creating a kubeconfig alone grants no rights. If you move networks, update `TF_VAR_allowed_cidr`, plan and apply through Terraform.

## Prove it

```bash
aws eks describe-cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" \
  --query 'cluster.{status:status,version:version,support:upgradePolicy.supportType,access:accessConfig,network:resourcesVpcConfig}'
aws eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name lab --region "$AWS_REGION" \
  --query 'nodegroup.{status:status,capacity:scalingConfig,ami:amiType}'
aws eks list-addons --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION"
(
  set -euo pipefail
  for LAB_ADDON in vpc-cni kube-proxy coredns eks-pod-identity-agent; do
    LAB_ADDON_STATUS="$(aws eks describe-addon --cluster-name "$CLUSTER_NAME" \
      --addon-name "$LAB_ADDON" --region "$AWS_REGION" \
      --query 'addon.{name:addonName,status:status,issues:health.issues}' --output json)"
    printf '%s\n' "$LAB_ADDON_STATUS"
    jq -e '.status == "ACTIVE" and ((.issues // []) | length == 0)' \
      <<< "$LAB_ADDON_STATUS"
  done
)
# Each of the four add-ons must appear above with ACTIVE, [] issues, and true.
# If a describe call or assertion fails, stop here and investigate that add-on.
kubectl --context "$LAB_KUBE_CONTEXT" auth can-i create deployments --all-namespaces
kubectl --context "$LAB_KUBE_CONTEXT" -n kube-system rollout status daemonset/eks-pod-identity-agent --timeout=180s
terraform plan -detailed-exitcode
```

Pass: one `Ready` node with `role=lab`; each of the four add-ons reports `ACTIVE` with no health issues (listing names alone is insufficient); explicit admin can create deployments; no Terraform changes (exit 0). Exit 2 means a drift/difference to explain. Add-on versions are discovered for this cluster version; a later plan can propose newer versions, so review that change before applying.

Explain aloud: Why do nodes need outbound connectivity? What does `endpoint_private_access=true` change? Which identity is authenticating `kubectl`? Why does `max_size=2` not itself add a second node? Why can an update temporarily increase billable node count? What will fail if you delete the IAM attachments before the resources using them?

## Cleanup, including a failed apply

Clean workloads and dynamic disks first. If you ran labs 09/10, finish their cleanup before this root. In particular, **keep the CSI controller, IAM permissions and cluster alive until EBS volume deletion is verified**. Also complete the cleanup in labs 11/12 if attempted. Merely setting node count to zero leaves control-plane charges running.

```bash
cd "$LAB_ROOT/run/07-eks-foundation"
# This also works after a partially failed apply; retain the state and actual inputs.
export CLUSTER_NAME="$(terraform output -raw cluster_name 2>/dev/null || printf '%s-arcade' "${TF_VAR_lab_id:-tfeks}")"
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
terraform state list
aws eks describe-cluster --name "$CLUSTER_NAME" --region "$TF_VAR_region"
```

Pass: state is empty and `describe-cluster` returns **ResourceNotFoundException**. Authentication/network errors are not proof of deletion. Never delete state files to make a failed destroy appear complete. Run the root cost/cleanup audit afterward.

[Hints](HINTS.md) · [Reference explanation](ANSWERS.md) · [Complete Terraform](solution/main.tf)

Sources: [EKS network requirements](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html), [endpoint access](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html), [access entries](https://docs.aws.amazon.com/eks/latest/userguide/creating-access-entries.html), [Kubernetes support versions](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html).
