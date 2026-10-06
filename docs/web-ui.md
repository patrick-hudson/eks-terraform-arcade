# Web workspace

Use the browser to launch real AWS resources, work through an incident and tear the environment down. This guide walks through one complete EKS session; [Launch real AWS labs](lab-launcher.md) has the matching terminal commands and other cloud lessons.

## Start the web runner

**For real AWS labs, start here.** The browser can create and remove the lab resources through Terraform; your terminal is where you inspect pods and edit the broken configuration. You can skip Game 00 and the simulated Practice desk.

From a Bash terminal:

```bash
cd ~/work/eks-terraform-examples
./arcade setup
./arcade serve --runner
```

`setup` installs the local tools; it does not create AWS resources. Keep the server terminal running. Open **[Launch real AWS labs](http://127.0.0.1:8765/#/guide/lab-launcher)** for the recommended path, including AWS login checks and the exact account, IAM and public-IP values you need. The steps below are the browser version of that path.

If port 8765 is occupied by an older Arcade server, stop that server with Ctrl-C and run it again with `--runner`. Alternatively, use `./arcade serve --runner --port 8766` and open [port 8766](http://127.0.0.1:8766). Browser notes are separate on each port; Terraform workspaces are shared.

## First session: EKS cluster → broken pod → cleanup

This creates a real EKS control plane and one EC2 worker in **us-west-2**, then a broken application to repair. Allow about **45–60 minutes including cluster setup**. The shared cluster is approximately **$0.15 for one hour / $0.30 for two hours**, before extra activity and provisioning/deletion time. See [the cost assumptions](cost-and-cleanup.md).

### 1. Create the cluster once

Open **[Game 07 → Environment](http://127.0.0.1:8765/#/lab/07-eks-foundation?tab=session)**.

1. Set **Starting point** to **starter**, then select **Prepare workspace**. This creates `run/07-eks-foundation/` with `versions.tf`, a provider lockfile and `BUILD.md`. **There is no cluster implementation yet.** Preparing these files creates nothing in AWS.
2. Open **Runbook** and write **`run/07-eks-foundation/main.tf`** in your editor. Building the cluster is the Game 07 exercise. Follow `BUILD.md` for the network, EKS cluster, worker, access and add-on requirements. Keep the supplied provider settings in `versions.tf`; add the `admin_principal_arn` and `allowed_cidr` inputs and all five required outputs in your Terraform. Use **Hints** if needed. Finish this implementation before selecting **Plan changes**.
3. Return to **Environment → Account & environment**. Enter your authenticated AWS profile, intended account ID, `us-west-2`, a unique resource prefix, permanent IAM user/role ARN and your public IPv4 followed by `/32`. Use the values collected in [the launch guide](lab-launcher.md), then choose **Save environment**.
4. Choose **Plan changes** and review **Saved plan**. The browser shows action metadata; use the saved-plan command below in a second terminal to inspect its full values. Confirm the intended account, one small worker, the restricted IP range and no NAT gateway or load balancer before applying. A plan with no cluster or worker means you have not finished the implementation.
5. Type the exact approval phrase shown, then choose **Apply reviewed plan**. **This is the step that creates billable AWS resources.** Wait for it to finish; a cluster can take 15–25 minutes to become ready.
6. Select **Submit repair** and read **Repair evidence**. Do not start a pod exercise until the foundation checks pass. If a check fails, use its expected/observed details and the Game 07 runbook to investigate.

To read the complete Game 07 plan after **Plan changes** finishes, run:

```bash
cd ~/work/eks-terraform-examples
source scripts/env.sh
terraform -chdir="$LAB_ROOT/run/07-eks-foundation" show arcade-apply.tfplan
```

Then return to the browser to approve that plan. After **Plan cleanup**, the corresponding file is `arcade-destroy.tfplan`.

**Optional shortcut:** choosing **guided** before preparing a new Game 07 workspace copies the complete reference Terraform. Use this only when you want to skip the cluster-building exercise and focus on pod incidents. An existing workspace keeps its original starting point and edits.

Keep Game 07 running while you work through an incident. Do not create a second cluster for each exercise.

### 2. Deploy the broken application

Open **[Incident 01 → Environment](http://127.0.0.1:8765/#/lab/11-incident-gauntlet%2Fscenario-01?tab=session)**.

1. Leave **Starting point** at **starter**, then choose **Prepare workspace**. This copies the intentionally broken application and its Terraform wrapper.
2. Under **Account & environment**, enter the **same profile, account and region as Game 07**, then choose **Save environment**. The runner reads the existing cluster connection.
3. Select **Plan changes**, review the plan, type the displayed approval and choose **Apply reviewed plan**.
4. Open **Workspace** or **Runbook** for the incident. A successful apply has deployed the failure; it does not mean the application is healthy.

Open a **second terminal** for diagnosis. These commands select the same isolated cluster connection used by the browser:

```bash
cd ~/work/eks-terraform-examples
source scripts/env.sh
source "$LAB_ROOT/run/07-eks-foundation/session-env.sh"
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 get pods
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-incident-01 describe pods -l app=incident
```

Expect the pod to fail to start. Collect the reason from the pod events, then edit **`run/scenario-01/candidate.yaml`** in your editor. This file is an input to Terraform. Return to **Environment → Plan changes → Apply reviewed plan** to deploy your repair. Use **Submit repair** and the runbook's HTTP check to prove that the application works. The **Coach** has progressive hints when you need them.

Do not rerun the runbook's manual workspace-creation commands after preparing through Environment. You already have the working copy; use its investigation, repair and acceptance instructions.

### 3. Delete the application, then the cluster

1. In **Incident 01 → Environment**, choose **Plan cleanup**. Review the deletion plan, type its exact `DESTROY` phrase and choose **Delete planned resources**.
2. Confirm the incident namespace is gone using its runbook checks. If you created other workloads on this cluster, clean those up too.
3. In **Game 07 → Environment**, repeat **Plan cleanup → review → type the displayed phrase → Delete planned resources**.
4. Follow the launch guide's final deletion checks: empty Terraform state and the named EKS cluster returning `ResourceNotFoundException`. Keep the workspace if any check fails.

**Closing a tab, stopping the server or marking a mission complete does not delete AWS resources.** Finish cleanup first. [The launch guide](lab-launcher.md) includes exact terminal cleanup commands and recovery steps.

## Work through a mission

Choose a lab from the directory, resume your current mission, or use **Surprise me** in the incident gauntlet. Incidents have neutral names so the directory does not disclose their causes. Open one incident at a time on your existing Game 07 cluster. Before starting, follow the displayed prerequisite Terraform setup order. The launcher links to each prerequisite; preparing its files does not verify live readiness. Complete its runbook checks before continuing.

The sidebar’s **Plain-English glossary** explains unfamiliar terms with practical examples. The questions ask you to make a decision and explain its effect; they do not require memorized definitions.

The **Workspace** view follows five stages:

1. **Brief:** define the delivery contract, prerequisites, cost and cleanup scope.
2. **Build:** follow the complete runbook to create the working copy and reach the initial state. An intended first failure is useful evidence.
3. **Investigate:** record a hypothesis, collect decisive evidence and make the smallest durable change.
4. **Verify:** run the full acceptance sequence and answer the interview reasoning check.
5. **Cleanup:** follow the dependency order, verify deletion and prepare your debrief.

Check each task only after doing it, then select **Record & continue**. You can jump to any stage, including cleanup, at any time. Completing all stages records mission completion. These task checks and written evidence remain self-reported. The separate **Environment** tab can run supported operations when the local runner is enabled, and stores repair receipts independently. Neither study completion nor a successful apply certifies teardown.

Use **Open complete runbook here** to read the source without leaving your stage. **Full-screen instructions** opens the **Runbook** view, and **Starter & reference files** opens **Files**. Command cards have copy buttons, but they are checkpoints rather than complete deployment scripts. Follow the launch guide for setup and shell activation; if Environment already prepared and applied the lab, continue at the runbook’s diagnosis steps instead of creating another working copy. Kubernetes repairs edit `candidate.yaml` and go through the workload’s Terraform plan and apply. Diagnostic `kubectl` reads are useful; manual patches and console edits do not count as the repair. The app cannot change your terminal environment.

The Workspace’s **Guided** study mode opens command checkpoints by default. This is separate from choosing **guided** as the Environment starting point. **Interview** mode initially collapses those details and prompts you to explain your hypothesis before seeking help. You can still open commands, hints and solutions. It is a practice preference, not a locked assessment or automatic score.

The older four-checkpoint session sidebar remains available on Runbook, Files, Hints, Solution and My notes. You can use it to record build/reproduction, explanation, verification and cleanup, then **Mark complete**. These checks share the mission record with the workspace; checking them does not fabricate individual task evidence or five-stage history.

## Other labs and environment controls

Use the [AWS launch guide](lab-launcher.md) to choose another real-cloud lab. Game 05 is a small serverless exercise without an EKS prerequisite; Game 13 adds a real internet path on your existing cluster. The browser, `./arcade session` CLI and `./arcade tui` share the same registered workspace, saved plan, inventory and repair receipt.

Built-in lifecycle controls support Games 00, 01, 03, 04, 05, 07, 08, 09, 10, 13 and incidents 11-01 through 11-10. Games 02, 06 and 12 use their complete runbooks for state migration, import and exercises spanning several labs.

Follow **Prepare these first** before starting a dependent lab. For missions with a **Terraform root** selector, each root has its own state: Games 09/10 use **Infrastructure** then **workload**; Game 13 uses **workload** then **access**. Configure, plan and apply each in that order; clean up in reverse. Returning to a prepared workspace preserves its edits and state.

Every apply uses the specific plan you reviewed. Changes to source, inputs, state or saved plan bytes require a new plan. Approval is bound to that plan's digest.

**Repair evidence** shows a dated pass, failure or incomplete result and each expected/observed check. It stays separate from study completion. Source or state changes make old evidence stale. Missions without an automated behavioral checker return incomplete evidence; Game 08 and Incident 08 also leave functional acceptance checks for the runbook. HTTP reachability, eviction and other operational tests may still require terminal work.

**Resource inventory** retains observed Terraform addresses, types, IDs and ARNs after failed operations and deletion. It excludes full state and secret values. **Cloud absence: unknown** means the retained inventory is not proof of deletion; keep the workspace and finish named-resource checks even when Terraform state is empty.

Jobs run one at a time and show bounded command-status events. Closing or navigating away from the tab does not cancel an operation; returning to Environment reconnects to its status while the server remains running. Browser events omit raw tool output. For a failed operation, keep state and investigate through the terminal and runbook before reviewing a fresh plan. After a server restart, inspect the retained session result and state before retrying. No automatic repair or timed cleanup runs.

The runner accepts only fixed operations for catalog missions and their declared roots. Mutations require the current local process’s capability token and valid Host/Origin checks. It is a local learner tool; it does not accept arbitrary shell commands or filesystem paths.

## Browse without enabling the runner

Run `./arcade serve` without `--runner` for read-only browsing. You can read runbooks, keep notes and use simulated drills without AWS credentials or an internet connection. Local session status is visible, but the browser cannot run lab operations. The server requires Python 3.10+ on Linux, macOS or WSL2 and accepts only loopback connections. No npm installation is required.

## Optional: practice without AWS

The **Practice desk** has four authored investigations and three Terraform plan-reading drills. Their observation output is simulated, and displayed diagnostic commands never execute. Open a brief, reveal one observation at a time, choose a decision and read the explanation. The debrief connects decisive evidence to a Terraform repair, recovery proof, cleanup and a changed-constraint interview question.

Select **Finish attempt** after choosing an answer to save a compact summary. Merely opening, refreshing or revisiting a drill does not record a completion. **New attempt** starts another repetition; completed attempts stay separate from the 24 hands-on mission records. The newest 20 summaries retain the drill, completion time, first-answer result, revealed observation IDs and practice duration. A drill result does not prove cloud health, cleanup, safety or mastery.

The desk suggests an incorrectly answered drill first, then a never-attempted drill, then the least recently completed one. It shows its reason and lets you choose freely. Export and restore preserve the summaries and current attempt; repeated restore does not duplicate attempts with the same ID.

For the same authored content in a terminal, use `./arcade drill list` or the [full-screen terminal workspace](tui.md). The Environment tab shows a value-free summary of a saved session plan. For other local plans, [the plan coach](plan-review.md) accepts Terraform show JSON through `./arcade review-plan PATH` or standard input. There is no plan-upload endpoint; raw plan values stay out of the browser.

## Appearance

Use **Appearance** in the header to select **System**, **Light** or **Dark**. System follows your device preference. Your choice persists on reload and leaves notes, study progress, repair receipts and workspaces intact.

## Hints, answers and evidence

The **Coach** panel reveals one investigation hint at a time. Hint bodies are requested only when revealed; on returning to a mission, the app fetches the levels you previously chose and restores them. It does not prefetch later levels. If loading fails, use **Retry saved hints**. Every mission provides three layers of investigation help.

The reasoning question appears in **Verify**. Select an option and choose **Check my reasoning** to receive correctness and an explanation. The public lesson response does not contain the answer index or explanation. This feedback tests understanding, not the resources in your account, and it does not gate stage completion.

Reference code and **Solution** require a deliberate reveal in the source reader. Reveals are practice aids, not security controls: the authored files remain on your computer. A direct solution link opens its reveal gate in a fresh page session. Source files are fetched on demand and cached within the page session; reload after editing a source file to see its new contents.

Use the **Evidence** panel to save the observed symptom, working hypothesis, decisive output, change, acceptance proof and deletion evidence. **My notes** holds freeform notes. Both save as you type. Avoid credentials, tokens and secrets.

**Export debrief** downloads a Markdown record containing structured evidence, freeform notes, discussion prompts, practice time and hints used. After a completed mission, **New attempt · keep evidence**, or **Practice again** in the older sidebar, resets stage selection, task/completion checks, hint counts and the practice clock. Notes, evidence and the selected practice mode remain. Export a debrief first if you want a separate record of the previous attempt.

## Prove the path users actually use

A green pod status or a port-forward is not the same as successful traffic through a Service. Incidents 09 and 10 require real HTTP responses: one repairs Service forwarding; the other must return the new version after an update stalls. Game 13 adds a real internet path restricted to your laptop’s public IPv4. It requires an external `curl` response and then evidence that the path closed after Terraform teardown. The web UI displays these requirements; it does not claim the live request happened.

## Practice time and cloud cost

The practice clock is optional. **Start / resume** begins elapsed time; **Pause** stops it. Its state survives navigation and reload, so a running clock also counts elapsed time while the page is closed. Pause it when you stop practicing. Completing the full guided workflow pauses its clock.

Environment shows separate **1-hour and 2-hour estimates**, with dated regional assumptions and activity-based costs under **What this estimate includes**. The one-worker EKS base is about **$0.149/hour** or **$0.30 for two hours**. Count the shared foundation once when working through multiple exercises; requests, storage, transfer and provisioning/deletion time can increase the total.

The clock measures practice time, not cluster lifetime or AWS charges. Pausing it, completing a mission, deleting a browser record or stopping the server does not stop infrastructure. The $20 figure is the whole curriculum’s planning allowance; the app does not read billing or enforce a cap. Follow [cost and cleanup](cost-and-cleanup.md), including backing-volume verification before foundation teardown.

## Save, export and restore progress

Study progress uses schema version 3 under the existing localStorage key `aws-interview-arcade:v1`. The key stays the same so existing version 1 and 2 notes and valid completion records migrate automatically. Simulated drill state is a separate field. Migration does not invent completed guided stages.

Session settings, saved-plan receipts, repair checks and retained resource inventory live in the ignored registered workspace, separately from browser progress. A browser progress export does not back up Terraform state, those receipts or AWS credentials. Preserve the workspace for recovery and cleanup.

Browser storage belongs to the browser profile and origin. `localhost` and `127.0.0.1`, different ports, and different browser profiles have separate records. Clearing site data removes progress; private browsing may discard it on close. If browser storage is unavailable or full, the app warns you and retains a temporary in-memory copy. Export before closing.

**Export progress** downloads a JSON backup of mission notes, evidence, checks, practice state and simulated drill attempts. It records a paused snapshot of each clock at export time; it does not pause the live clock in your current session. **Restore backup** reads a version 1, 2 or 3 JSON file locally, previews how many records can merge, and waits for **Merge backup**. The file is not uploaded. The maximum accepted size is 20 MiB (shown as 20 MB in the interface).

Restore merges complete mission records by update time. A newer record wins; an equal or older backup record leaves the current browser record intact. Unknown mission IDs are skipped. It does not combine conflicting text field by field, so export your current progress before merging valuable alternate notes. Restored clocks are paused and do not accrue the time between export and restore.

Updates from another tab are merged by record timestamp. The app tells you when another tab changes progress; reopen the mission to load its latest details. This is local browser coordination, not account or device sync.

## Local verification

The Python suite covers the source catalog, guided lesson content, hint/answer boundaries, read-only defaults and guarded runner jobs. JavaScript tests cover session rendering, stale-plan approval, themes, progress migration, task completion, timers, repeat attempts and backup merging. Node 18+ is used only for development; it is not needed to run the workspace.

```bash
python3 -m unittest discover -s web/tests -p 'test_*.py' -v
node --test web/tests/*.test.cjs
```

The HTTP tests use temporary fixtures and an ephemeral loopback port. No test provisions AWS infrastructure. See [the validation record](VALIDATION.md) for executed checks and their limitations, and [learning design](learning-design.md) for the teaching contract.

The server exposes approved authored files, fixed learning/toolchain/session endpoints and an explicit list of web assets. Session responses include selected metadata from registered workspaces; the file API remains restricted to authored content. It does not serve directory listings, `run/`, state, plan files, actual tfvars or arbitrary filesystem paths. Vendored Markdown libraries run locally and retain their licenses in `web/vendor/`; see `web/THIRD_PARTY_NOTICES.md` for versions and sources.
