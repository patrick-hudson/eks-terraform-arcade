# Terminal practice desk

Run `./arcade tui` from a real terminal. Python's standard-library curses provides the full-screen purple interface. You can browse all 24 missions, read their runbooks, navigate prerequisite setup and complete the seven offline drills without cloud credentials.

Wide terminals show a mission or drill preview beside the list; narrower terminals use one column. Use arrows and Enter to select, **Tab** to switch missions and drills, **b** or Left to go back, **?** for help and **q** to quit. Long runbooks, observations and feedback scroll with arrows or Page Up / Page Down. Resizing preserves your place; terminals below 60 columns by 18 rows show resize guidance. A noninteractive terminal or Python without curses returns useful CLI alternatives immediately.

## Environment support

| Missions | Terminal workflow |
| --- | --- |
| 00 | Prepare, plan, apply, inspect outputs and destroy using local `terraform_data`; no AWS |
| 01, 03, 04, 05, 07 | Registered single-root Terraform lifecycle, explicit AWS identity and saved-plan approval |
| 08, 11-01 through 11-10 | Terraform workload lifecycle bound to the registered Game 07 cluster and isolated context |
| 02, 06, 09, 10, 12, 13 | Browse, prepare available authored modes and follow the explicit runbook handoff for environment operations |
| 11 overview | Runbook navigation to the individual incidents |

Preparation uses the existing lab launcher and never evaluates a recipe's shell text. It preserves existing edits and state. Starter modes may deliberately require you to write or repair code before Terraform can plan; use the runbook's contract. Guided mode is available only where authored.

A mission's detail view shows prerequisite setup order and links directly to each prerequisite. **Prepared files do not prove live readiness.** Workload operations check the registered Game 07 identity, EKS status, four add-ons and Ready workers. Those observations are snapshots; complete the runbook's acceptance checks too.

## Review and execute an operation

1. Choose **Prepare** for the intended mode, then **Configure**. Paid operations require a named authenticated AWS profile, intended 12-digit account and `us-west-2`. Infrastructure missions also require a distinctive lab ID. Game 07 asks for your permanent IAM role/user ARN and public IPv4 `/32`.
2. Choose **Plan changes**. The desk temporarily restores the normal terminal so Terraform can stream init, validation and planning output. Review the human-readable saved plan and the value-free plan coach summary.
3. Choose **Apply saved plan**. Confirm the displayed workspace, account, profile, region and operation. Type exactly `APPLY 123456789012`, substituting your account. Game 00 uses `APPLY LOCAL`. Anything else cancels.
4. Choose **Verify** to inspect local Terraform state and outputs. Workloads also list pods in the explicit context. Read the linked mission for its required HTTP, API, permission and absence checks; a green apply is not mission acceptance.
5. Choose **Plan destroy**, review it, then **Apply saved plan** with `DESTROY 123456789012` or `DESTROY LOCAL`. A destroy plan has its own review and approval.

The runner applies only the saved binary. Its receipt binds the digest, source and input fingerprint, state snapshot, registered workspace, operation, account/profile/region and Kubernetes context. Edited source, copied workload-module files, changed inputs, state, context or plan bytes require a fresh plan. It checks AWS STS again before execution, passes arguments without a shell, and ignores ambient Terraform variable/argument overrides and AWS credential environment overrides in favor of the named profile.

Explicit inputs live in the ignored workspace's `arcade.auto.tfvars.json`; lifecycle settings and plan receipts are alongside it. Edit the Terraform input file or working source to make mission repairs, then plan again. Saved binary plans can contain sensitive values: keep them local alongside state. The plan coach stores no extra JSON plan file.

## Authored incident starting states

**Game 04 guided preparation** persists `policy_variant = "broken"`. Repair that input explicitly after investigating the policy boundary.

**Game 05 guided preparation** persists `table_environment_key = "COUNTER_TABLE"` in `arcade.auto.tfvars.json`. This deliberately preserves the initial runtime fault. The interface does not repair it. After diagnosis, explicitly change that Terraform input to `TABLE_NAME` and review a new plan.

**Scenario 11-10** starts with `baseline.yaml` copied to `candidate.yaml`. Its first plan and approval create the healthy baseline. **Verify** then checks rollout readiness, diagnostic-pod readiness and the exact internal Service HTTP response `arcade-10-v1`. Only after that proof does **Prepare broken update** become usable: it rechecks v1 and copies the authored broken update into `candidate.yaml`, retaining the same state. Plan and approve that update separately. No repair is copied. If you already edited or applied a scenario outside this workflow, follow its runbook rather than letting the terminal overwrite those files.

The baseline preflight checks the authored one-worker shape and prints node requests and other workloads for review. Complete other exercise cleanup before continuing; the baseline readiness check confirms that the healthy version can actually run. Internal Service HTTP is not internet-access proof.

## Kubernetes activation and recovery

After successful Game 07 apply, the runner writes `kubeconfig.json` inside that registered workspace. Its distinct context, explicit profile and account/region binding leave your default kubeconfig untouched. **Show / save shell activation** prints safely quoted exports for both `KUBECONFIG` and `LAB_KUBE_CONTEXT`, plus matching AWS/Terraform identity variables, and saves a sourceable `session-env.sh`. Source the printed absolute path in your shell before running the existing context-only diagnostic commands.

Terraform runs outside curses; pressing Enter restores the desk after success, failure or interruption. The runner never automatically destroys or repairs resources. Keep the workspace after partial apply or failed cleanup, inspect state and the runbook, then generate and review a fresh plan for the intended recovery operation. Do not delete state to clear an error.

Game 07 destroy refuses active or unknown registered dependent workspaces, including the complex missions whose cleanup remains in their runbooks. Missing state is unknown, not evidence of absence. Empty local state still cannot establish AWS cleanup: finish named-resource absence, disks and externally created resource checks before closing the session. The $20 total allowance and shared-account ownership boundaries continue to apply.

Development verification uses fake AWS/kubectl runners and a real, disposable Game 00 Terraform lifecycle. It creates no AWS resources and is not live cloud acceptance evidence.
