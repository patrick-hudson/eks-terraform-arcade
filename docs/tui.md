# Run AWS labs from the terminal

Use the TUI to create an EKS cluster, deploy a broken app, review a Terraform repair and destroy the environment. **Start with Game 07 in starter mode and write the cluster Terraform yourself, then move to Incident 11-01.** You do not need to complete any local exercises first.

For a command-by-command alternative, use [Launch an AWS lab](lab-launcher.md). This page follows the terminal interface's actual menu labels.

## Before you open the TUI

From your checkout (adjust the path if needed):

```bash
cd ~/work/eks-terraform-examples
./arcade setup
source scripts/env.sh
./arcade doctor
```

Already installed the tools? Skip `setup`; still source `scripts/env.sh` in each new terminal. Complete [AWS authentication and account checks](setup.md#3-authenticate-and-pin-the-intended-account) and [the EKS preflight](setup.md#4-check-eks-support-and-capacity-before-game-07). Setup does not sign you into AWS or grant permissions.

Have these values ready for the configuration prompts:

| Prompt | What to enter |
| --- | --- |
| AWS profile | Your authenticated profile name; `default` is valid if that is the intended account |
| Intended AWS account (12 digits) | The account you mean to use; compare it with the STS identity check in setup |
| AWS region | `us-west-2` |
| Distinctive lab ID | A unique lowercase name for this session, such as `study-oct05`; keep it for cleanup |
| Permanent IAM role/user ARN | Your IAM user or role ARN, not an `arn:aws:sts:…:assumed-role/…` session ARN |
| Your public IPv4 /32 | The public IPv4 from setup with `/32` appended; this permits your workstation to reach the EKS API |

The default one-worker cluster is estimated at **$0.15 for one hour / $0.30 for two hours**, before extra usage. Incidents share that cluster, so count the foundation once. Creation and deletion take billable time; reserve 20–30 minutes for cleanup. See [cost assumptions](cost-and-cleanup.md). There is no automatic shutdown or hard spending cap.

## First session: Game 07, then Incident 11-01

Start the TUI from the project directory:

```bash
./arcade tui
```

### 1. Create the cluster

Use arrows and Enter, or press **/**, type `07`, then Enter to keep the search and Enter again to open the mission. Choose these actions in order:

1. **Read mission runbook** — read the required cluster resources, inputs, outputs and readiness checks.
2. **Prepare starter: Author the platform** — copies `versions.tf`, `.terraform.lock.hcl` and `BUILD.md` into `run/07-eks-foundation/`. The cluster implementation is deliberately missing.
3. **Write `run/07-eks-foundation/main.tf` in your editor.** Follow `BUILD.md` to define the network, IAM roles, EKS cluster, worker, add-ons and required outputs. Use the [Game 07 hints](../labs/07-eks-foundation/HINTS.md) if you get stuck. Finish this implementation before planning; preparing or configuring the workspace does not write it for you.
4. **Configure account, profile and required inputs** — enter the values above.
5. **Plan changes and review saved plan** — Terraform checks your code and displays exactly what it proposes to create. Verify the account, region, one `t3.medium` worker, your `/32`, and no NAT gateway or load balancer. Fix any missing implementation or validation errors in your working source, then plan again.
6. **Review / apply saved plan (typed confirmation)** — type the displayed `APPLY` phrase with your account number. **This creates billable AWS resources.** Allow time for the cluster and worker to start.
7. **Submit repair / check observed behavior** — inspect the results and finish the runbook's readiness checks: a Ready worker, four healthy add-ons, administrator access and a plan with no remaining changes.
8. **Show / save shell activation for isolated context** — saves the environment file needed for diagnostic commands below.

The optional **Prepare guided: Reference foundation** action copies the completed cluster code when you want to concentrate on pod incidents. It skips the authoring part of Game 07; starter is the exercise path.

Each operation temporarily leaves the full-screen view to show its output. Press Enter when prompted to return. Opening a mission or preparing its files does not create a cluster. If the menu instead shows **Resume prepared workspace (preserve edits and state)**, this checkout already has a workspace; that action preserves it rather than switching its preparation mode.

Use a **second terminal** for editing while the TUI stays open. After the cluster apply succeeds and you select the shell activation action, activate that same cluster in this terminal:

```bash
cd ~/work/eks-terraform-examples
source scripts/env.sh
source run/07-eks-foundation/session-env.sh
kubectl --context "$LAB_KUBE_CONTEXT" get nodes -o wide
```

Only source `session-env.sh` after the activation action creates it. Use the absolute path printed by that action if your checkout is elsewhere. Keep this terminal for editing and `kubectl`; keep the first terminal for the TUI.

### 2. Deploy the broken app

Return to the mission list with **b**. Clear the previous search with **/** then **Ctrl-U**, type `11-01`, and press Enter twice. In **Incident 01**:

1. Choose **Read mission runbook**, then **Prepare starter: Broken incident**.
2. Choose **Configure account, profile and required inputs**. Use the same profile, account and `us-west-2`; the session uses the registered Game 07 cluster.
3. Choose **Plan changes and review saved plan**, then **Review / apply saved plan (typed confirmation)**. Review only the incident's namespace and objects before approving.

This is a separate apply from the cluster setup. A successful apply creates the intended broken exercise; it does not mean the app is healthy. In the second terminal:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 get pods -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 describe pods -l app=incident
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 get events --sort-by=.metadata.creationTimestamp
```

Expect a stalled release and investigate its events. The [incident runbook](../labs/11-incident-gauntlet/scenario-01/README.md) has progressive hints and acceptance checks. Write down the decisive observation before opening a hint.

### 3. Repair through Terraform

Edit **`run/scenario-01/candidate.yaml`** in your editor. This file is an input to the incident's Terraform code. Use `kubectl` to inspect the workload; make the lasting repair in that working file.

Return to Incident 01 in the TUI. Choose **Plan changes and review saved plan**, then **Review / apply saved plan (typed confirmation)** again. Choose **Submit repair / check observed behavior** and complete the runbook's HTTP and no-change-plan checks. A receipt marked **UNKNOWN**, failed or stale is not proof of recovery.

This incident tests traffic inside Kubernetes. Choose [Game 13](../labs/13-public-access/README.md) later to practice reaching the app through its public address from your workstation.

### 4. Delete the incident, then the cluster

In **Incident 01**, choose **Plan destroy / review cleanup before applying**. Inspect the deletion plan, then choose **Review / apply saved plan (typed confirmation)** and type the displayed `DESTROY` phrase. Submit the checks again and verify that the incident namespace is gone. Press **i** to inspect retained resource IDs or **c** for the exact cleanup instructions.

When you are done with all cluster exercises, repeat those actions for **Game 07**. Complete the runbook's named-resource deletion checks, including AWS reporting that the exact cluster no longer exists. If another incident or workload still exists, clean it up before the foundation.

**Quitting the TUI leaves AWS running.** Keep the workspace, state and inputs until deletion is verified. If an apply or cleanup fails halfway, reopen the same mission, inspect its state and create a fresh plan; do not delete files to clear the error.

## Keyboard controls

Wide terminals show a mission or drill preview beside the list; narrower terminals use one column. Resizing preserves your place; terminals below 60 columns by 18 rows show resize guidance. A noninteractive terminal or Python without curses returns useful CLI alternatives immediately.

| Control | Action |
| --- | --- |
| Up / Down, Enter | Select and open a mission, drill or action |
| Tab | Switch missions and offline drills from the desk |
| / | Search titles, IDs, symptoms and runbook text from the desk |
| Enter / Escape while searching | Keep the filter / restore the previous filter |
| Backspace / Ctrl-U while searching | Delete a character / clear the filter |
| c / r / i from a mission | Open cleanup / repair evidence / retained resource inventory |
| b / Left / Escape | Go back |
| ? / h | Open help |
| q | Quit |
| Page Up / Page Down, Home / End | Scroll or jump through lists and long text |

Search keeps its filter when you return from a mission. While the search field is active, letters such as `q` are search text, not shortcuts.

## Environment support

| Missions | Terminal workflow |
| --- | --- |
| 00 | Prepare, plan, apply, check the applied contract and destroy using local `terraform_data`; no AWS |
| 01, 03, 04, 05, 07 | Registered single-root Terraform lifecycle, explicit AWS identity and saved-plan approval |
| 08, 11-01 through 11-10 | Terraform workload lifecycle bound to the registered Game 07 cluster and isolated context |
| 09, 10 | Select infrastructure (`.`) then `workload`; output wiring and dependency checks use the registered Game 07 foundation |
| 13 | Select `workload` then `access`; the access root requires your public IPv4 `/32` |
| 02, 06, 12 | Browse, prepare available authored modes and follow the complete ordered runbook for migration, import or multi-lab operations |
| 11 overview | Runbook navigation to the individual incidents |

Preparation uses the existing lab launcher and never evaluates a recipe's shell text. It preserves existing edits and state. Starter modes may deliberately require you to write or repair code before Terraform can plan; use the runbook's contract. Guided mode is available only where authored.

The mission screen shows the session state, next action and 1-hour / 2-hour estimates. Its detail actions include cost assumptions, repair evidence, retained IDs/ARNs, the last operation and cleanup commands. Count the shared EKS foundation once across concurrent exercises; usage charges remain extra and there is no hard billing cap. A mission's detail view shows prerequisite setup order and links directly to each prerequisite. **Prepared files do not prove live readiness.** Workload operations check the registered Game 07 identity, EKS status, four add-ons and Ready workers. Those observations are snapshots; complete the runbook's acceptance checks too.

## Other missions and plan safeguards

For Games 09, 10 and 13, use **Select Terraform root** to choose the directory Terraform operates on. Each directory has its own state and plan. Configure and apply them in the order shown in the prerequisite list, then reverse that order for cleanup. A prerequisite entry opens that mission directly.

Cloud missions with a checker make bounded read-only observations when you choose **Submit repair / check observed behavior**. Others report **UNKNOWN** and point to their runbook. Game 08 and Incident 08 have additional functional checks; finish the HTTP, permission, eviction or deletion checks the runbook requires. These receipts do not set browser study-completion checkboxes. Optional Game 00 uses `APPLY LOCAL` and `DESTROY LOCAL` because it creates no AWS resources.

The runner applies only the saved binary. Its receipt binds the digest, source and input fingerprint, state snapshot, registered workspace, operation, account/profile/region and Kubernetes context. Edited source, copied workload-module files, changed inputs, state, context or plan bytes require a fresh plan. It checks AWS STS again before execution, passes arguments without a shell, and ignores ambient Terraform variable/argument overrides and AWS credential environment overrides in favor of the named profile.

Prior repair evidence becomes stale after relevant source or state changes. After editing, plan and apply the repair before submitting again. **UNKNOWN** means the available observations did not establish the result; it does not mean success.

Explicit inputs live in the ignored workspace's `arcade.auto.tfvars.json`; lifecycle settings and plan receipts are alongside it. Edit the Terraform input file or working source to make mission repairs, then plan again. Saved binary plans can contain sensitive values: keep them local alongside state. The plan coach stores no extra JSON plan file.

## Authored incident starting states

**Game 04 guided preparation** persists `policy_variant = "broken"`. Repair that input explicitly after investigating the policy boundary.

**Game 05 guided preparation** persists `table_environment_key = "COUNTER_TABLE"` in `arcade.auto.tfvars.json`. This deliberately preserves the initial runtime fault. The interface does not repair it. After diagnosis, explicitly change that Terraform input to `TABLE_NAME` and review a new plan.

**Scenario 11-10** starts with `baseline.yaml` copied to `candidate.yaml`. Its first plan and approval create the healthy baseline. **Verify healthy baseline before broken update** then checks rollout readiness, diagnostic-pod readiness and the exact internal Service HTTP response `arcade-10-v1`. Only after that proof does **Prepare broken update** become usable: it rechecks v1 and copies the authored broken update into `candidate.yaml`, retaining the same state. Plan and approve that update separately. No repair is copied. If you already edited or applied a scenario outside this workflow, follow its runbook rather than letting the terminal overwrite those files.

The baseline preflight checks the authored one-worker shape and prints node requests and other workloads for review. Complete other exercise cleanup before continuing; the baseline readiness check confirms that the healthy version can actually run. Internal Service HTTP is not internet-access proof.

## Kubernetes activation and recovery

After successful Game 07 apply, the runner writes `kubeconfig.json` inside that registered workspace. Its distinct context, explicit profile and account/region binding leave your default kubeconfig untouched. **Show / save shell activation** prints safely quoted exports for both `KUBECONFIG` and `LAB_KUBE_CONTEXT`, plus matching AWS/Terraform identity variables, and saves a sourceable `session-env.sh`. Source the printed absolute path in your shell before running the existing context-only diagnostic commands.

Terraform runs outside curses; pressing Enter restores the desk after success, failure or interruption. The runner never automatically destroys or repairs resources. Keep the workspace after partial apply or failed cleanup, inspect state and the runbook, then generate and review a fresh plan for the intended recovery operation. Do not delete state to clear an error.

Game 07 destroy refuses active or unknown registered dependent workspaces, including missions with manual runbook steps. Games 09 and 10 destroy `workload` before infrastructure; Game 10 also requires backing-volume absence before removing CSI. Game 13 destroys `access` before `workload`. The inventory retains observed Terraform addresses, types, IDs and ARNs across failed operations and destruction. It omits full state, outputs and secret values. Missing state is unknown, not evidence of absence. Empty local state still cannot establish AWS cleanup: finish named-resource absence, disks and externally created resource checks before closing the session. The $20 total allowance and shared-account ownership boundaries continue to apply.

Development tests use fake AWS/kubectl runners and a real, disposable Game 00 Terraform lifecycle. Those checks are local evidence. The separate [validation record](VALIDATION.md) reports live cloud tests, cleanup and remaining limitations; local tests alone do not establish cloud acceptance.
