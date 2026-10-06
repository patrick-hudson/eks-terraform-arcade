# Launch an AWS lab

**Start here: Game 07 → Incident 11-01.** Write the Terraform for a real EKS cluster with one EC2 worker, deploy a broken pod, investigate it and repair it through Terraform. No local exercises are required.

This is the **command-line walkthrough**. Prefer menus? Use the [TUI walkthrough](tui.md#first-session-game-07-then-incident-11-01) or [browser walkthrough](web-ui.md). They use the same workspaces; choose one route to start.

| Step | What happens | Creates AWS resources? |
| --- | --- | --- |
| Prepare | Copies the lab files into `run/` | No |
| Configure | Saves your account, profile and access settings | No |
| Plan | Reads AWS and shows proposed Terraform changes | No |
| Apply | Runs the reviewed changes after you type approval | **Yes** |
| Submit | Checks what is actually running | No |
| Plan destroy → Apply | Reviews and deletes this lab's resources | Deletes them |

Budget about **$0.15 for one hour / $0.30 for two hours** for the shared cluster at the [documented Oregon rates](cost-and-cleanup.md). Creation and deletion time count; requests, transfer and extra resources add cost. Game 07 has a 45–60 minute practice time box, but writing the infrastructure may take longer. Write and check the code before applying; reserve 20–30 minutes for cleanup afterward. Closing Arcade does not stop billing.

## 1. Open a terminal in the project

Run **every command on this page from the project directory**, one block at a time. Use your checkout's actual path if different:

```bash
cd ~/work/eks-terraform-examples
source scripts/env.sh
./arcade doctor
```

If tools are missing, run `./arcade setup`, source `scripts/env.sh` again, then rerun `./arcade doctor`. See [tool installation](setup.md#2-install-tools-and-activate-a-lab-terminal) if setup itself fails.

## 2. Choose your AWS account and access

Use the **authenticated profile that Terraform can use**. Replace `default` below if yours has another name. If you are not signed in, follow [AWS login setup](setup.md#3-authenticate-and-pin-the-intended-account), then return here. An existing CLI browser login may need that guide's process-profile bridge for Terraform.

```bash
export AWS_PROFILE=default
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION=us-west-2
export TF_VAR_region=us-west-2
aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json
read -r -p 'Type the intended 12-digit AWS account ID: ' TF_VAR_expected_account_id
export TF_VAR_expected_account_id
test "$(aws sts get-caller-identity --query Account --output text)" = "$TF_VAR_expected_account_id" \
  && printf 'Account matches. Continue.\n' \
  || printf 'STOP: account check failed. Fix the profile before continuing.\n'
```

Continue only after **Account matches**. Other resources in this account are fine: Terraform manages this lab's separate state. Do not import or delete existing account resources to get past a lab error.

EKS needs the **permanent IAM user or role ARN** behind your login. If the identity above starts with `arn:aws:iam::` and contains `:user/`, use it. If it contains `:assumed-role/`, use the role lookup under [Troubleshooting](#troubleshooting) below; an STS session ARN will not work.

```bash
read -r -p 'Permanent IAM role/user ARN for EKS access: ' TF_VAR_admin_principal_arn
export TF_VAR_admin_principal_arn
export TF_VAR_lab_id="arcade$(date +%m%d%H%M)"
PUBLIC_IP=$(curl -4 -fsS https://checkip.amazonaws.com)
export TF_VAR_allowed_cidr="$PUBLIC_IP/32"
printf 'Lab name: %s\nAllowed workstation IP: %s\n' "$TF_VAR_lab_id" "$TF_VAR_allowed_cidr"
```

The `/32` allows only your current public IPv4 address to reach the cluster API. Keep this lab name, profile and region through cleanup. Complete the [EKS support and capacity checks](setup.md#4-check-eks-support-and-capacity-before-game-07) before the first apply; your identity also needs permission to create EKS, EC2 networking and IAM roles. Signing in alone does not grant those permissions.

## 3. Build and create the EKS cluster — Game 07

**You write this cluster's Terraform.** Prepare the starter and save your real account/access inputs:

```bash
./arcade session prepare 07 --mode starter
./arcade session configure 07 \
  --profile "$AWS_PROFILE" --account-id "$TF_VAR_expected_account_id" \
  --region us-west-2 --lab-id "$TF_VAR_lab_id" \
  --admin-principal-arn "$TF_VAR_admin_principal_arn" \
  --allowed-cidr "$TF_VAR_allowed_cidr"
```

Open **`run/07-eks-foundation/BUILD.md`** for the requirements. Preparation supplies `versions.tf` (provider versions, account guard and tags) and its lockfile. Configuration saves your inputs in `arcade.auto.tfvars.json`. **It does not supply `main.tf` or create a cluster.**

Create **`run/07-eks-foundation/main.tf`** in your editor. Work through these pieces using the [Game 07 requirements](../labs/07-eks-foundation/README.md) and [progressive hints](../labs/07-eks-foundation/HINTS.md):

| Write | What it must accomplish |
| --- | --- |
| Input declarations | Declare `admin_principal_arn` and `allowed_cidr` as strings; use the configured values. Keep the existing account, region and lab-ID variables in `versions.tf`. |
| Networking | A separate VPC, two public subnets in different availability zones, an internet gateway and routes. No NAT gateway. |
| Cluster identity and access | EKS IAM role, a cluster named `${var.lab_id}-arcade`, EKS 1.37 with standard support, your explicit IAM administrator access entry, private node access and public API access limited to your `/32`. |
| Worker | Node IAM role, launch template and managed node group named `lab`: one `t3.medium`, 20 GiB encrypted gp3 disk, label `role=lab`; follow the full contract's disk, metadata and credit settings. |
| Add-ons | VPC CNI, kube-proxy, CoreDNS and Pod Identity agent. These provide networking, DNS and pod identity support; follow the required bootstrap order. |
| Outputs | `cluster_name`, `region`, `vpc_id`, `node_role_arn` and `cluster_security_group_id`, used by later exercises and cleanup. |

Skip the runbook's manual `mkdir`/`cp` section: Arcade already prepared this workspace. **Stop here to write the code before continuing.** An empty/no-change plan before the first deployment means you have not built the infrastructure yet.

When your implementation is ready:

```bash
terraform -chdir=run/07-eks-foundation fmt
./arcade session plan 07
```

`session plan` runs Terraform initialization and validation, then saves a plan. Fix syntax or configuration errors and rerun it. **Check the plan:** your account, `us-west-2`, one EKS cluster, one `t3.medium` worker, a 20 GiB disk and two public subnets. Expect IAM roles and networking too. There should be **no NAT gateway or load balancer**. The API allows your workstation's `/32`; it is not open to everyone.

```bash
./arcade session apply 07
```

Review the displayed plan and type **`APPLY <your-account-ID>`** when prompted, replacing the angle-bracket text with your 12 digits. This is where AWS resources start being created. Wait for the operation to finish.

**Optional shortcut:** for a fresh workspace, `./arcade session prepare 07 --mode guided` supplies the reference implementation instead of starter. Use it only if you choose to skip writing the cluster this time. It does not switch or overwrite an existing prepared workspace. The build-it-yourself path above remains the exercise.

## 4. Connect kubectl and check readiness

A successful cluster apply creates a connection file inside the lab directory. Activate it in this terminal:

```bash
source run/07-eks-foundation/session-env.sh
kubectl --context "$LAB_KUBE_CONTEXT" get nodes -L role -o wide
./arcade session submit 07 | jq '.repair | {status,checks}'
```

Expect **one Ready node** and repair status **`pass`**. The submit checks include the cluster, worker, four add-ons and administrator access. If status is `fail` or `unknown`, read its checks and fix setup before launching an incident. A successful shell exit alone does not mean the checks passed.

In a new terminal, first `cd` back to the project and source both `scripts/env.sh` and `run/07-eks-foundation/session-env.sh`. This selects the lab's isolated Kubernetes connection. You do not need to run `aws eks update-kubeconfig`.

## 5. Launch the broken pod — Incident 11-01

Keep the same cluster running. This creates the exercise's own namespace (a named space for its Kubernetes objects), not another EKS cluster.

```bash
./arcade session prepare 11-01 --mode starter
./arcade session configure 11-01 \
  --profile "$AWS_PROFILE" --account-id "$TF_VAR_expected_account_id" \
  --region us-west-2
./arcade session plan 11-01
./arcade session apply 11-01
```

Review and approve this second plan. Then inspect the failure:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 get pods
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 \
  rollout status deployment/app --timeout=45s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 get events --sort-by=.metadata.creationTimestamp
```

**The rollout timeout is intentional.** The app should fail to pull its image (`ErrImagePull` or `ImagePullBackOff`). A Terraform apply can succeed while its application is broken. Authentication errors or an unreachable cluster are setup problems, not this incident.

## 6. Diagnose, edit and apply your repair

Read the [incident brief](../labs/11-incident-gauntlet/scenario-01/README.md) and reveal [hints](../labs/11-incident-gauntlet/scenario-01/HINTS.md) only as needed. Write down the event that explains the failure.

Open **`run/scenario-01/candidate.yaml`** in your editor and make the repair there. Terraform reads this file as its workload input. Keep `kubectl` for inspection; do not repair with `kubectl edit`, `patch` or `apply`.

```bash
./arcade session plan 11-01
./arcade session apply 11-01
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 \
  rollout status deployment/app --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 \
  wait --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 exec arcade-diagnostics -- \
  wget -T 10 -qO- http://app.arcade-incident-01.svc.cluster.local:8080/
./arcade session submit 11-01 | jq '.repair | {status,checks}'
./arcade session plan 11-01
```

Pass: the rollout finishes, the HTTP request returns the app's response, submit reports **`pass`**, and the final plan has **no changes**. This HTTP check is inside Kubernetes. For an app you reach through a public address from your workstation, do [Game 13](../labs/13-public-access/README.md) next.

## 7. Delete the incident, then the cluster

Do this even if you did not solve the exercise. Keep the project files and Terraform state until deletion is verified.

**Delete Incident 11-01 first:**

```bash
./arcade session plan_destroy 11-01
./arcade session apply 11-01
./arcade session submit 11-01 | jq '.repair | {status,checks}'
terraform -chdir=run/scenario-01 state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace arcade-incident-01
```

Type **`DESTROY <your-account-ID>`** at the apply prompt. Expect empty state, a passing cleanup receipt and a **NotFound** namespace response. NotFound is expected here; permission or connection errors are not proof of deletion.

If you want another incident now, keep the cluster, prepare that incident's ID and follow its own runbook. Remove each workload when finished. When ending practice, delete all remaining dependent workloads before Game 07.

**Capture the cluster's IDs, then delete Game 07:**

```bash
export LAB_CLUSTER_NAME=$(terraform -chdir=run/07-eks-foundation output -raw cluster_name)
export LAB_VPC_ID=$(terraform -chdir=run/07-eks-foundation output -raw vpc_id)
./arcade session plan_destroy 07
./arcade session apply 07
./arcade session submit 07 | jq '.repair | {status,checks}'
terraform -chdir=run/07-eks-foundation state list
aws eks describe-cluster --name "$LAB_CLUSTER_NAME" --region us-west-2
bash scripts/audit-aws.sh
```

Expect empty state and **ResourceNotFoundException** for this exact cluster. Inspect the audit for leftover lab resources; it is read-only and may list unrelated resources in a shared account. Its zero exit status alone does not certify that every listed resource is gone. Use the [cleanup guide](cost-and-cleanup.md) to interpret it. Do not delete other people's resources.

If an apply fails partway, keep its workspace and use the same plan-destroy/apply workflow. If the ID outputs are unavailable, use the retained inventory (`./arcade session status 07`) and [Game 07 recovery instructions](../labs/07-eks-foundation/README.md#cleanup-including-a-failed-apply). Never delete state to clear an error.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `aws`, `terraform` or `kubectl`: command not found | Run `./arcade setup`, then `source scripts/env.sh` in this terminal. |
| Expired login or Terraform cannot find credentials | Renew the selected profile; see the [browser-login bridge](setup.md#3-authenticate-and-pin-the-intended-account). |
| Plan/apply says AccessDenied | Read the denied action. Ask for the provisioning permissions required by this lab; do not change unrelated resources. |
| Game 07 has no cluster resources in its plan | Starter supplies the provider setup, not the cluster implementation. Write `run/07-eks-foundation/main.tf` as described in step 3, then plan again. A no-change plan is not readiness proof. |
| Workload says its foundation is missing | Finish Game 07 apply and readiness checks first, using the same profile, account and region. |
| kubectl cannot reach the cluster after changing networks | Your public IP may have changed. Update Game 07's `allowed_cidr` in `run/07-eks-foundation/arcade.auto.tfvars.json` to the new IPv4 `/32`, then plan and apply Game 07. |
| Apply says the plan changed or is stale | Run `session plan` again, review the new plan and approve that version. For deletion, use `session plan_destroy`. |

**Find the permanent role ARN when STS reports an assumed role:**

```bash
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)
ASSUMED_ROLE=${CALLER_ARN#*:assumed-role/}
ROLE_NAME=${ASSUMED_ROLE%%/*}
aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text
```

Run this lookup only for an `:assumed-role/` identity. Copy the returned IAM ARN into the prompt in step 2. If `iam:GetRole` is denied, obtain it from your administrator. Do not replace `sts` with `iam` in the session ARN: IAM roles can have paths that the session ARN omits.

## What to run next

- **More EKS break/fix:** [ten incidents](../labs/11-incident-gauntlet/README.md), reusing Game 07. Incident 11-10 has a healthy-baseline step before its broken update.
- **Broken public access:** [Game 13](../labs/13-public-access/README.md); follow its workload → access setup order and reverse it for cleanup.
- **Real AWS without a cluster:** [Game 05](../labs/05-serverless-counter/README.md) uses Lambda and DynamoDB. Choose guided preparation to reach its configuration fault quickly.
- **Other commands, preparation modes and recovery:** [launcher/session reference](launcher-reference.md). Games 09, 10 and 13 have more than one Terraform directory; Games 02, 06 and 12 use ordered manual runbooks.
