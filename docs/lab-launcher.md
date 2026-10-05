# Prepare and run labs with Arcade

`arcade start` prepares a working directory and prints the commands for the selected mission. It does not sign in, initialize Terraform, contact AWS, apply Kubernetes manifests, or create cloud resources. This makes it useful for setting up a challenge before starting the AWS billing clock. The separate `arcade session` commands, TUI and opt-in browser runner provide the supported execution workflow.

The launcher knows the exact files each exercise needs. It keeps the broken starts, copies acceptance tests where appropriate, and uses the same `run/` paths as the mission runbooks. Your edits, state, evidence and saved plans belong in those working directories.

## Start from any directory

Load the project environment once in each terminal. The installed shell PATH also exposes `arcade`; sourcing the environment supplies the variables needed by the printed Terraform and Kubernetes commands.

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
cd /tmp
arcade labs
arcade start 00
arcade next 00
arcade status
```

`start 00` creates `$LAB_ROOT/run/00-contracts`, with the broken Terraform and its acceptance tests. It works from `/tmp` because the launcher resolves its own project directory. Nothing is applied. Read the printed steps, run the first plan, record its failure, and repair your working copy.

Use the alias in the catalog or the full mission ID:

```bash
arcade start 05 --mode guided
arcade start 11-01
arcade next 11-incident-gauntlet/scenario-01
arcade labs --json
arcade status --json
```

The first command above prepares the Lambda architecture with the **faulty initial configuration selected in its printed plan command**. The incident command prepares `run/scenario-01/candidate.yaml`, the Terraform root and the shared workload module. It does not copy the repair. Terraform owns the namespace, workload and small diagnostic pod used for HTTP checks.

## Pick how much code you want supplied

| Mode | What you receive | Good for |
|---|---|---|
| `starter` | Broken files or a provider guard plus requirements, depending on the exercise | Writing Terraform, forming a diagnosis, practicing without the answer |
| `guided` | Reference infrastructure, with the exercise's injected fault still enabled where applicable | Reviewing architecture, reaching the debugging problem sooner |

The default is `starter`. Game 08 and the ten incidents have only a starter mode, because their useful starting point is the broken workload. Games 11 and 12 are runbooks: use `arcade next 11` or `arcade next 12` to see the prerequisites and open their full instructions. They do not create another cluster or a duplicate set of state files.

Guided mode is an explicit choice to copy solution code. Game 00 guided mode includes the fixed contract; 01–03 and 07 include complete reference Terraform. Games 04 and 05 print the fault flag for their initial plan. Games 09 and 10 copy reference AWS infrastructure plus the **broken** Kubernetes workload. Game 06 still requires you to solve import, drift and the address refactor; its moved-block answer is not copied.

The launcher is a starting aid, not a replacement for the assignment. Each command sequence links back to its runbook for acceptance, investigation and recovery. If a runbook begins with `mkdir` and `cp` setup instructions, skip that initial copy section after using `arcade start`: your working files are already prepared. Do not copy fresh starter files over your repair.

## Keep sessions and state intact

Starting an already registered lab resumes the same workspace without replacing any file. `arcade next` reprints its steps and cleanup instructions. You cannot switch an existing workspace from starter to guided with another `start` command, and the launcher does not adopt a pre-existing directory that it did not create. That includes a manually prepared workspace with valuable Terraform state.

```bash
arcade start 00
# If already prepared, this resumes the existing mode and leaves your files alone.
arcade next 00
arcade status
```

If a directory already exists from earlier practice, keep using its original runbook. Finish and verify teardown before organizing a new attempt. Preserve the whole directory until cleanup succeeds, including hidden files and state backups. Do not delete `.arcade-session.json` to try to switch modes: that removes the launcher's registration, not AWS resources.

Status reports local workspace evidence. It can count managed objects in readable local Terraform state; it reports uncertainty for remote, unreadable or unsupported state. A zero count, an absent state file, or an absent workspace does **not** certify cloud cleanup. Dynamic EBS volumes and a Game 06 fixture that was never imported can exist outside that state.

The status command reads local files only. It does not refresh state or test AWS authentication. The broader `arcade doctor` command checks installed prerequisites; use the existing smoke or verification utilities when you intentionally want read-only AWS checks.

## Before running cloud commands

Use the AWS profile you already authenticated. Choose the real account and retain the same lab ID, region and profile through cleanup. The project's preferred region is `us-west-2`; sourcing `env.sh` preserves values you have already set, so check them if you previously practiced elsewhere.

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
export AWS_PROFILE=default
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION=us-west-2
export TF_VAR_region=us-west-2
# Set TF_VAR_expected_account_id to your intended account's actual 12-digit ID.
: "${TF_VAR_expected_account_id:?Export the intended account ID}"
: "${TF_VAR_lab_id:?Keep one distinctive lab ID through cleanup}"
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

If `default` is not your authenticated profile, substitute its actual name. Never place access keys or passwords in recipes, evidence or chat. See [AWS testing setup](aws-testing.md) for browser sign-in and the profile bridge used by Terraform.

A shared account is supported by the exercise's separate state, account guard, tags and lab names. Terraform does not automatically adopt every resource in that account. Before applying, review the saved plan and resolve any unexpected resource address, name collision, quota or permission error. Do not import an existing shared-account resource simply to make a lab succeed.

Game 07 additionally needs your permanent IAM role/user ARN and your actual current public IPv4 `/32`. The launcher prints these setup checkpoints and never fabricates an account, principal or IP. Games 08–13 reuse that cluster. The context check in each recipe is an opportunity to confirm that `kubectl` is targeting the disposable arena.

## Shared session commands

From the checkout, `./arcade session --help` lists the command-line interface. It uses the same session service as `./arcade tui` and the browser’s **Environment** tab. Ordinary `./arcade serve` displays local status read-only; `./arcade serve --runner` explicitly enables browser operations.

```bash
./arcade session catalog
./arcade session status 05
./arcade session status 09 --root workload
```

These commands read local files only and return JSON. Session status includes available operations, prerequisites, next action, 1-hour/2-hour estimates, the reviewed plan, retained resource metadata and the latest repair receipt. It does not refresh AWS or certify live readiness. There is no `--json` flag: session results already use JSON, and operation diagnostics go to standard error.

For a local Game 00 lifecycle:

```bash
./arcade session prepare 00 --mode starter
# Repair run/00-contracts/ using its runbook; its first plan is meant to fail.
./arcade session plan 00
./arcade session apply 00       # Review the summary; type APPLY LOCAL.
./arcade session submit 00
./arcade session plan_destroy 00
./arcade session apply 00       # Review the cleanup summary; type DESTROY LOCAL.
./arcade session submit 00
```

For a guided serverless exercise, use the same profile, account and distinctive lab ID confirmed in preflight:

```bash
./arcade session prepare 05 --mode guided
./arcade session configure 05 \
  --profile "$AWS_PROFILE" --account-id "$TF_VAR_expected_account_id" \
  --region us-west-2 --lab-id "$TF_VAR_lab_id"
./arcade session plan 05
./arcade session apply 05
# Diagnose, edit Terraform inputs/source, then plan and apply the repair.
./arcade session submit 05
./arcade session plan_destroy 05
./arcade session apply 05
./arcade session submit 05
```

`prepare` preserves a registered workspace and its mode. `configure` saves explicit inputs without applying them. `plan` initializes, validates and saves a plan; `plan_destroy` saves a separate deletion plan. `apply` prints the review and asks for `APPLY <account>` or `DESTROY <account>` as appropriate. Game 00 uses `LOCAL`. The receipt binds approval to source, inputs, state, identity and saved plan bytes. Changed or consumed plans need a new review.

For an explicitly supplied approval, both flags are required. Read `plan.reviewText`, `plan.approval` and `plan.digest` in `session status`, set `REVIEWED_PLAN_DIGEST` to the digest you reviewed, then run:

```bash
./arcade session apply 05 \
  --approval "APPLY $TF_VAR_expected_account_id" \
  --plan-digest "$REVIEWED_PLAN_DIGEST"
```

Do not reuse that digest for another plan or cleanup. Omitting `--approval` uses the interactive review and confirmation instead.

Game 07 configuration additionally requires `--admin-principal-arn` and `--allowed-cidr`, using your permanent IAM role/user ARN and current public IPv4 `/32`:

```bash
./arcade session configure 07 \
  --profile "$AWS_PROFILE" --account-id "$TF_VAR_expected_account_id" \
  --region us-west-2 --lab-id "$TF_VAR_lab_id" \
  --admin-principal-arn "$TF_VAR_admin_principal_arn" \
  --allowed-cidr "$TF_VAR_allowed_cidr"
```

Prepare Game 07 first, set those inputs from the [setup guide](setup.md), and inspect its plan before approval. EKS workloads must use the registered foundation’s account, profile, region and isolated Kubernetes context.

### Select the Terraform root

Games 09 and 10 use `--root .` for AWS infrastructure, then `--root workload` for Kubernetes resources. Game 13 uses `--root workload` first, then `--root access`. Configure, plan, apply and submit each root separately; carry the same `--root` through cleanup. Selecting a root never executes a command by itself.

For example, after applying Game 09’s infrastructure and verifying its outputs:

```bash
./arcade session configure 09 --root workload \
  --profile "$AWS_PROFILE" --account-id "$TF_VAR_expected_account_id" \
  --region us-west-2
./arcade session plan 09 --root workload
./arcade session apply 09 --root workload
./arcade session submit 09 --root workload
```

The session wires Game 09’s fixture from actual infrastructure outputs and checks Game 10’s CSI prerequisite. Game 13’s `access` configuration additionally needs `--allowed-cidr`; its worker identity comes from the registered foundation. Cleanup reverses root order: 09/10 workload before infrastructure, 13 access before workload. Keep CSI until the storage volume’s absence is established, and keep Game 07 until all dependents are gone.

### Read the result and finish the runbook

`submit` collects bounded observations without applying a repair. It records **pass**, **fail** or **unknown**, with expected and observed evidence. Source or state changes mark the prior receipt stale. A successful apply alone never passes an exercise, and repair receipts remain separate from the browser’s self-reported study progress. Missions without an automated behavioral checker report unknown and retain the runbook’s acceptance steps. After destruction, submit checks the cleanup phase where supported; the inventory’s unknown absence field still requires named-resource checks.

`verify` normally performs the same observation as `submit`. Incident 11-10 has a special sequence: apply its healthy baseline, run `./arcade session verify 11-10`, then `./arcade session begin_incident 11-10`. The latter rechecks baseline HTTP behavior and prepares the authored broken update; plan and approve that update separately. It does not copy a repair.

Supported lifecycle missions are 00, 01, 03, 04, 05, 07, 08, 09, 10, 13 and incidents 11-01 through 11-10. Games 02, 06 and 12 retain complete ordered runbooks for migration, import and multi-lab work. Their available preparation steps do not turn manual runbook commands into automatic operations.

Session inventory retains managed Terraform addresses, types, IDs and ARNs plus the last operation result; it excludes full state and secret values. Failed apply/destroy retains this cleanup context. Keep the entire workspace, resolve the failure and review a fresh recovery plan. An empty state or retained inventory alone does not prove cloud absence.

## Dependencies change the command sequence

| Mission | Checkpoint you must follow |
|---|---|
| 00 | Local-only contract test; no AWS credentials required |
| 02 | Bootstrap the backend first, initialize the workload with that actual bucket, test lock contention, then destroy/migrate the workload before deleting the backend |
| 04–05 | Guided setup uses the printed fault flag; a green apply is the beginning of diagnosis |
| 06 | Create and record exactly one new fixture manually, then import it; empty Terraform state cannot clean up a fixture that was never imported |
| 07 | Inspect account, principal, API CIDR, node count and costs before apply; wait for the node and all required add-ons |
| 08 / 11 | Review and apply the broken workload through Terraform; edit candidate.yaml, review/apply the repair, prove real behavior, then use Terraform destroy |
| 09 | Create AWS identity first, generate workload/fixture.yaml from its real output, then apply the workload root; destroy that root before its AWS role and association |
| 10 | Check the disk driver before the broken claim; follow the controlled Terraform replacement procedure, then use cleanup.sh to verify disk deletion before removing the driver |
| 11-10 | Require a healthy v1 baseline before applying the broken v2 update in the same Terraform state |
| 12 | Reuse the existing Game 08 workload root/state; never create a second owner for arcade-app |
| 13 | Preflight from the laptop, then separate access/workload states; close and verify external access before removing the healthy app |

Printed commands are instructions, never an automatically executed queue. Run one checkpoint at a time. Stop on unexpected failures. Intentional rollout timeouts, failed Jobs, denied negative checks and `NotFound` cleanup responses are identified in the corresponding mission. A setup/authentication error is not evidence that you reproduced its intended fault.

## Costs and teardown

`arcade start`, `next`, `labs` and `status` are local and free of AWS charges. Running the commands they print can create billable resources. The whole curriculum has a **$20 allowance**, not a billing cap; the one-node EKS arena has a base estimate of **$0.149/hour** or **$0.30 for two hours** at the documented us-west-2 assumptions, including time spent creating and deleting it. Count the shared foundation once across exercises; storage, requests, transfer and retries add to the base. Keep it only while actively practicing.

Every prepared mode prints cleanup steps. Most Terraform missions use a reviewed saved destroy plan. Backend migration, unmanaged fixtures and EBS lifecycle have distinct cleanup paths and are not reduced to a generic destroy command. Always finish the exact runbook's absence checks. Deleting pods or reducing nodes to zero leaves the EKS control plane running.

At session end: use each workload’s Terraform root to remove attempted application/incident namespaces, complete Pod Identity and EBS cleanup while the cluster is alive, destroy their separate Terraform roots, then destroy Game 07 and perform the [cost and cleanup audit](cost-and-cleanup.md). Keep all relevant working directories until that verification completes.

`lab-recipes.json` is the shared authored catalog used by the CLI, TUI and browser. It contains explicit copy lists and printable command strings. It contains no shell hooks, credentials, live account inventory or background cleanup scheduler.

## Terraform owns the Kubernetes exercise

Arcade copies an explicit set of module and root files into each working directory. Edit `candidate.yaml`; the wrapper reads it as Terraform input. `kubectl` remains useful for events, logs, permissions checks and diagnostic requests. Do not repair with `kubectl patch`, `kubectl apply`, a console edit or a manual namespace deletion. The maintenance eviction in Incident 08 is an operational test, not its repair.

Games 09 and 10 have two Terraform roots: the top-level directory owns AWS dependencies, and `workload/` owns Kubernetes resources. Game 13 has `access/` and `workload/`. Status reports these declared roots and does not mistake the copied `workload-module/` for another state.

For Game 13, `starter` includes the deliberately wrong access rule. `guided` is the worked reference: the external request should already succeed after setup. In both modes preflight supplies the real account, worker and laptop address; no account IDs, IPs or credentials are embedded in the recipe.

The launcher never overwrites an existing prepared workspace. If you prepared an old manifest-only version before this update, the repeated `start` command preserves it. Complete its original cleanup, then use a fresh prepared workspace; do not layer a new Terraform owner over live objects from the old attempt.

### Recover after a partial Game 09 or 10 setup

If infrastructure setup fails before the workload was configured, select the `workload` root and choose **Plan cleanup**. The session can resolve the existing Game 07 account and connection without requiring the missing bucket or storage-driver outputs. Review and approve that workload destroy plan, even if it creates an empty state, then plan infrastructure cleanup.

This configuration permits cleanup only. Use normal **Configure** after infrastructure succeeds before planning a new workload. A missing state file still means unknown ownership; never delete files or state to bypass the dependency check. If the Game 07 connection is unavailable, preserve the workspace and recover it using the mission runbook.
