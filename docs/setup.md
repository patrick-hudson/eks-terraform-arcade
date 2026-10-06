# Setup and account preflight

For the complete real AWS launch sequence, use [Launch an AWS lab](lab-launcher.md). This page supplies tool installation, login and account checks. The preferred region is **us-west-2 (Oregon)**. A shared account is supported; follow the [ownership and cleanup rules](cost-and-cleanup.md).

## 1. Choose your launch interface

Use the [command-line walkthrough](lab-launcher.md), [terminal workspace](tui.md) or [browser runner](web-ui.md). All three use the same Terraform workspaces. Start with Game 07 in starter mode, write its cluster Terraform, then launch Incident 11-01; local exercises are optional.

The root `arcade` entry requires Bash and Python 3.10+. It works from the project directory before PATH activation. The TUI also requires Python's standard-library curses module. Install the lab tools below before provisioning AWS.

## 2. Install tools and activate a lab terminal

The verified installer targets Linux and WSL2 and needs Bash, Python3, curl, unzip, tar, sha256sum and GPG already installed. From the checkout:

```bash
./arcade setup
source scripts/env.sh
./arcade doctor
```

Downloads go into this project's `.tools/`; the installer does not need sudo, edit shell startup files or sign you into AWS. On macOS, use the official vendor installers or Homebrew for Terraform, AWS CLI, matching kubectl and jq. Keep kubectl within one minor version of the EKS API server. The [toolchain record](toolchain.md) lists pinned versions and checked release sources.

Source `scripts/env.sh` in each lab terminal, using its absolute path when elsewhere. `./arcade env` prints the quoted activation command. This sets `LAB_ROOT`, adds `.tools/bin` to PATH and supplies lab defaults. It preserves an existing AWS profile and region. It does not change your directory or choose an account. Follow each mission's explicit `cd` command into its own `run/` directory; keep reference solutions unchanged.

Explicitly select Oregon before paid work:

```bash
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_VAR_region="$AWS_REGION"
aws --version
terraform version
kubectl version --client
```

Those version checks run locally. The environment change affects only this shell and its child processes.

## 3. Authenticate and pin the intended account

Use an authenticated named profile appropriate for your account. For IAM user or role browser login, follow [the AWS testing guide](aws-testing.md) to grant the browser-login permission and scoped Game 05 operator permissions. Sign in yourself; never paste credentials in chat.

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
export TF_VAR_kubernetes_version=1.37
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

The reference uses **EKS 1.37**, confirmed by the us-west-2 AWS API and the [October 2026 release announcement](https://aws.amazon.com/about-aws/whats-new/2026/10/amazon-eks-distro-kubernetes-version-1-37/), with standard support ending **December 1, 2027 (UTC)**. kubectl **1.37.1** matches this target. The check above fails if the chosen version is absent or outside standard support. Before applying, recheck add-on/client compatibility whenever you choose a newer version. The cluster support policy is `STANDARD`; it is not an expiration timer. One t3.medium uses 2 vCPUs; two use 4. Other running instances also consume the quota. Capacity/organization restrictions can block launches even when quota is sufficient.

## 5. Prepare prerequisites in order

Before a live exercise, run `./arcade start ID` or `./arcade next ID` from the checkout, or open it in `./arcade tui`. The browser's mission view also lists prerequisite environments. Follow the numbered prerequisite setup commands before returning to the exercise. Prepared files, a session receipt or a local state count are not proof that the environment works in AWS.

Game 07 supplies the cluster for Games 08–13 and the individual incidents. Keep its state and use the mission's own working directory for each dependent workload. For multi-root runbooks, follow their internal order: Game 09 creates its AWS resources before the workload; Game 10 creates AWS resources and proves the storage controller ready before the workload; Game 13 creates the workload before public access and removes access before the workload.

The CLI, TUI and browser runner manage Games 00, 01, 03, 04, 05, 07, 08, 09, 10, 13 and incidents 11-01 through 11-10. Games 02, 06 and 12 use ordered manual runbooks; see the [support matrix](tui.md#environment-support). Game 05 guided mode deliberately retains its starting fault until you repair the Terraform input. Incident 11-10 needs a healthy v1 baseline and live readiness/HTTP proof before its separately reviewed broken update. Neither shortcutting prerequisite verification nor an empty namespace reproduces that update incident.

## 6. Standard apply and cleanup loop

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
