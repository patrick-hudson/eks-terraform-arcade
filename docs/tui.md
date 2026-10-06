# Terminal practice desk

Run `./arcade tui` from a real terminal. Python's standard-library curses provides the full-screen purple interface. You can browse all 24 missions, read their runbooks, navigate prerequisite setup and complete the seven offline drills without cloud credentials.

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

## Review and execute an operation

1. Choose **Prepare** for the intended mode. For Games 09, 10 and 13, use **Select Terraform root** and follow its prerequisite order. Configure each root before planning. Paid operations require a named authenticated AWS profile, intended 12-digit account and `us-west-2`. Standalone infrastructure missions also require a distinctive lab ID. Game 07 asks for your permanent IAM role/user ARN and public IPv4 `/32`; Game 13’s access root asks for the `/32` too.
2. Choose **Plan changes**. The desk temporarily restores the normal terminal so Terraform can stream init, validation and planning output. Review the human-readable saved plan and the value-free plan coach summary.
3. Choose **Apply saved plan**. Confirm the displayed workspace, account, profile, region and operation. Type exactly `APPLY 123456789012`, substituting your account. Game 00 uses `APPLY LOCAL`. Anything else cancels.
4. Choose **Submit repair / check observed behavior**. Game 00 checks the applied Terraform contract. Cloud missions with a checker make bounded read-only observations; others report **UNKNOWN** and point to the runbook. Game 08 and Incident 08 leave functional acceptance steps explicit. Read the receipt’s expected and observed results, then complete any required HTTP, permission, eviction or absence checks. A green apply is not mission acceptance, and these receipts do not set browser study-completion checkboxes.
5. Choose **Plan destroy**, review it, then **Review / apply saved plan** with `DESTROY 123456789012` or `DESTROY LOCAL`. A destroy plan has its own review and approval. Submit again after destruction for the available cleanup checks, then finish the runbook’s named-resource absence checks.

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
