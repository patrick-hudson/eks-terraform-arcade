# Setup and account preflight

The preferred workload region is **us-west-2 (Oregon)**. Use a disposable sandbox account and a named AWS profile. The app runs locally and costs nothing; the commands you apply in AWS are billable.

## 1. Activate this project

For this checkout, run this in each existing terminal you want to use for labs:

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
mkdir -p "$LAB_ROOT/run"
```

This sets `LAB_ROOT` to the script's actual project folder, adds `.tools/bin` to `PATH`, and supplies lab defaults. It preserves an existing `AWS_PROFILE` and region. If you previously selected another region, explicitly choose Oregon for this session:

```bash
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_VAR_region="$AWS_REGION"
```

On this machine, the installed Bash startup block makes the tools and `arcade` command available in new Bash terminals. An already-open terminal needs the `source` command above once. Source the environment again when a new terminal needs the lab variables. Run each mission’s explicit `cd` commands before its relative Terraform commands; putting binaries on PATH does not choose a state directory. It does not sign you in, change your current directory, or choose an AWS account.

For an extracted copy elsewhere, source its `scripts/env.sh` by absolute path instead. `run/` holds your own state and evidence; keep reference solutions unchanged.

## 2. Install or verify tools

```bash
arcade doctor
aws --version
terraform version
kubectl version --client
```

These checks run locally. Terraform **1.16.5**, AWS CLI **2.37.9**, kubectl **1.36.5**, jq **1.8.2**, and kubeconform **0.8.0** are installed under `.tools`. The existing Python **3.12.3** runs the app; it needs Python 3.10 or later and no pip packages. Node is only used for development tests. See the [toolchain record](toolchain.md) for checked release sources.

To reproduce the Linux/WSL installation in a fresh copy:

```bash
cd "$HOME/work/eks-terraform-examples"
bash scripts/bootstrap-tools.sh
source scripts/env.sh
arcade doctor
```

The bootstrap script checks official downloads before installing them. It requires Bash, Python3, curl, unzip, tar, sha256sum, and GPG. On macOS, use the official vendor installers or Homebrew for Terraform, AWS CLI, matching kubectl and jq; the supplied binary bootstrap targets Linux. Keep kubectl within one minor version of the EKS API server.

To start the web app from any directory:

```bash
arcade serve
```

Open **http://127.0.0.1:8765**. If it is already open and serving this kit, reuse it. Ctrl-C stops the local app, not any AWS resources.

## 3. Authenticate and pin the intended account

You already use an IAM user or role and do not need to establish SSO just for this kit. Follow [the AWS testing guide](aws-testing.md) to grant the browser-login permission and scoped Game 05 operator permissions. Sign in yourself; never paste credentials in chat.

Use fresh profile names if these already belong to another account:

```bash
aws login --profile arcade-browser --region us-west-2
aws configure set credential_process \
  'aws configure export-credentials --profile arcade-browser --format process' \
  --profile arcade-smoke
aws configure set region us-west-2 --profile arcade-smoke
export AWS_PROFILE=arcade-smoke
aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json
read -r -p 'Type the intended 12-digit sandbox account ID: ' TF_VAR_expected_account_id
export TF_VAR_expected_account_id
ACTUAL_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
test "$ACTUAL_ACCOUNT" = "$TF_VAR_expected_account_id"
```

The process profile lets Terraform obtain temporary credentials through AWS CLI browser login. Do not execute `export-credentials` directly; its output is secret. Renew with `aws login --profile arcade-browser`. If you already have a suitable authenticated named profile, use its name instead of creating these two profiles. The [AWS testing guide](aws-testing.md) also includes SSO instructions for accounts that use it.

**Stop if the account comparison fails.** Type the account ID you intend to use; do not derive the expected ID from the current credentials. Every AWS provider also sets `allowed_account_ids`.

A sandbox provisioning role needs permissions for the services the selected lab creates, including IAM role creation, attachment and `iam:PassRole`. EKS also needs service-linked role creation if the account has never used it. Lab04 needs IAM simulation APIs. Organization SCPs, permission boundaries and quotas can still block these operations. This kit grants narrow application-role permissions; it does not ship an all-powerful bootstrap IAM user or access keys.

For EKS, select the permanent IAM role or user ARN your credentials represent. `aws sts get-caller-identity` often returns an **STS session ARN**, which cannot be used as an EKS access-entry principal. Obtain the original role ARN through your organization or `aws iam get-role`; retain any role path, including Identity Center's reserved path. Do not mechanically replace `sts` with `iam`.

```bash
read -r -p 'Permanent IAM role/user ARN for EKS administrator access: ' TF_VAR_admin_principal_arn
export TF_VAR_admin_principal_arn
PUBLIC_IP=$(curl -fsS https://checkip.amazonaws.com)
export TF_VAR_allowed_cidr="$PUBLIC_IP/32"
```

Run from a network that can reach the EKS public API and keep its egress IP stable. VPN/proxy changes can invalidate the CIDR; update it in Terraform if needed. Private cluster access remains on for workers.

## 4. Check EKS support and capacity before game 07

```bash
aws eks describe-cluster-versions --region "$AWS_REGION" \
  --query 'clusterVersions[].{Version:clusterVersion,Status:versionStatus,StandardUntil:endOfStandardSupportDate}'
export TF_VAR_kubernetes_version=1.36
EKS_SUPPORT=$(aws eks describe-cluster-versions --region "$AWS_REGION" \
  --cluster-versions "$TF_VAR_kubernetes_version" \
  --query 'clusterVersions[0].versionStatus' --output text)
if [ "$EKS_SUPPORT" != STANDARD_SUPPORT ]; then
  printf 'Stop: EKS %s is not in standard support in this region.\n' "$TF_VAR_kubernetes_version"
  exit 1
fi
aws ec2 describe-instance-type-offerings --region "$AWS_REGION" \
  --location-type availability-zone --filters Name=instance-type,Values=t3.medium
aws service-quotas get-service-quota --service-code ec2 \
  --quota-code L-1216C47A --region "$AWS_REGION" \
  --query 'Quota.{Name:QuotaName,Value:Value}'
```

The reference uses **EKS 1.36**, the latest EKS version listed on October 4, 2026, with standard support ending **August 2, 2027**. Upstream Kubernetes 1.37.1 is newer but is not the EKS target. The check above fails if the chosen version is absent or outside standard support. Before applying, recheck add-on/client compatibility whenever you choose a newer version. The cluster support policy is `STANDARD`; it is not an expiration timer. One t3.medium uses 2 vCPUs; two use 4. Other running instances also consume the quota. Capacity/organization restrictions can block launches even when quota is sufficient.

## 5. Standard apply and cleanup loop

Inside the lab's **run** directory:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=apply.tfplan
terraform show apply.tfplan
terraform apply apply.tfplan
terraform plan
```

Read the proposed creates/updates/deletes and resource counts before applying the saved plan. Never apply a saved plan after a later configuration change; produce a fresh one. Use the mission's variable flags for fault mode instead of this generic plan command.

When done, follow the lab-specific cleanup (especially Kubernetes/PVCs), then:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
```

Destroy may need retries after dependencies finish deleting. Keep the working directory, state, inputs and credentials until service-native verification confirms deletion. Empty Terraform state does not prove controller-created resources are gone. No blanket `rm -rf run/` shortcut.

Source: [kubectl version skew](https://kubernetes.io/releases/version-skew-policy/), [EKS versions](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html), [EKS access entries](https://docs.aws.amazon.com/eks/latest/userguide/creating-access-entries.html).
