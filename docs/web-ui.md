# Web workspace

The local workspace contains 24 hands-on missions (14 games and ten individual incidents) and seven separate simulated drills. The hands-on five-stage workflow contains 120 stages, 240 task checkpoints, 72 progressive investigation hints and 24 interview reasoning checks. It reads the same runbooks and code files you can open in your editor.

## Start and stop

Use Python 3.10 or newer on Linux, macOS or WSL2. From the project root:

```bash
./arcade serve
```

Open **[the Practice desk](http://127.0.0.1:8765/#/practice)** and keep that terminal running. This default mode is read-only: it displays authored content and local session status without running lab operations. No npm installation, AWS credentials or internet connection is needed to browse or use simulated drills. External documentation and actual lab commands have their usual internet requirements.

If the port is occupied:

```bash
./arcade serve --port 8766
```

Then open [the alternate local port](http://127.0.0.1:8766). The server accepts only loopback connections. Press Ctrl-C in its terminal to stop it. **Stopping the server leaves any AWS resources you created running.** Finish the mission’s cleanup instructions separately.

## Practice before provisioning

The **Practice desk** has four authored investigations and three Terraform plan-reading drills. Their observation output is simulated, and displayed diagnostic commands never execute. Open a brief, reveal one observation at a time, choose a decision and read the explanation. The debrief connects decisive evidence to a Terraform repair, recovery proof, cleanup and a changed-constraint interview question.

Select **Finish attempt** after choosing an answer to save a compact summary. Merely opening, refreshing or revisiting a drill does not record a completion. **New attempt** starts another repetition; completed attempts stay separate from the 24 hands-on mission records. The newest 20 summaries retain the drill, completion time, first-answer result, revealed observation IDs and practice duration. A drill result does not prove cloud health, cleanup, safety or mastery.

The desk suggests an incorrectly answered drill first, then a never-attempted drill, then the least recently completed one. It shows its reason and lets you choose freely. Export and restore preserve the summaries and current attempt; repeated restore does not duplicate attempts with the same ID.

For the same authored content in a terminal, use `./arcade drill list` or the [full-screen terminal workspace](tui.md). The Environment tab shows a value-free summary of a saved session plan. For other local plans, [the plan coach](plan-review.md) accepts Terraform show JSON through `./arcade review-plan PATH` or standard input. There is no plan-upload endpoint; raw plan values stay out of the browser.

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

Use **Open complete runbook here** to read the source without leaving your stage. **Full-screen instructions** opens the **Runbook** view, and **Starter & reference files** opens **Files**. Command cards have copy buttons, but they are checkpoints rather than complete deployment scripts: first run the source’s setup, exports and working-directory commands. Kubernetes repairs edit `candidate.yaml` and go through the workload’s Terraform plan and apply. Diagnostic `kubectl` reads are useful; manual patches and console edits do not count as the repair. The app cannot change your terminal environment.

**Guided** mode opens command checkpoints by default. **Interview** mode initially collapses those details and prompts you to explain your hypothesis before seeking help. You can still open commands, hints and solutions. It is a practice preference, not a locked assessment or automatic score.

The older four-checkpoint session sidebar remains available on Runbook, Files, Hints, Solution and My notes. You can use it to record build/reproduction, explanation, verification and cleanup, then **Mark complete**. These checks share the mission record with the workspace; checking them does not fabricate individual task evidence or five-stage history.

## Operate the environment

Install tools with `./arcade setup`, authenticate your named AWS profile, then restart the local server with the runner explicitly enabled:

```bash
./arcade serve --runner
```

Open a mission’s **Environment** tab. The browser, `./arcade session` CLI and `./arcade tui` use the same registered workspace, plan, inventory and repair receipt. The browser supports lifecycle operations for Games 00, 01, 03, 04, 05, 07, 08, 09, 10, 13 and incidents 11-01 through 11-10. Games 02, 06 and 12 retain their complete ordered runbooks for the deliberate state migration, import and multi-lab steps. Game 11 links to its incidents.

1. Read **Prepare these first** and follow each prerequisite link. Preparing files does not make infrastructure ready.
2. Select **Starting point** and **Prepare workspace**. Returning to a prepared workspace preserves its edits and state. For a multi-root mission, choose the **Terraform root**: Games 09/10 use Infrastructure (`.`) then `workload`; Game 13 uses `workload` then `access`.
3. Open **Account & environment** and **Save environment** for each root. Supply a named authenticated profile, intended account and `us-west-2`. Standalone AWS labs require a unique resource prefix. Game 07 also needs your permanent IAM role/user ARN and public IPv4 `/32`; Game 13’s access root needs the `/32`. Never paste access keys into the form.
4. Choose **Plan changes** and review **Saved plan**. The summary shows resource actions and uncertainty while omitting values. Review private plan details in the terminal when needed. Type the exact displayed phrase, such as `APPLY 123456789012` or `APPLY LOCAL`, then choose **Apply reviewed plan**. Changes to source, inputs, state or saved plan bytes require a new plan; approval is bound to the reviewed plan digest.
5. Diagnose with the mission runbook, edit Terraform inputs/source or `candidate.yaml`, then plan and apply the repair. Choose **Submit repair** to collect bounded observations without changing deployed infrastructure. Read every failed or incomplete check and any **Needs a new check** marker.
6. Choose **Plan cleanup**, review the separate deletion plan and type its `DESTROY` phrase. Follow **Before you leave** and the complete cleanup commands in dependency order, then submit for available cleanup observations and perform the remaining absence checks.

**Repair evidence** shows a dated pass, failure or incomplete result and each expected/observed check. It stays separate from study completion. Source or state changes make old evidence stale. Missions without an automated behavioral checker return incomplete evidence; Game 08 and Incident 08 also leave functional acceptance checks for the runbook. HTTP reachability, eviction and other operational tests may still require terminal work.

**Resource inventory** retains observed Terraform addresses, types, IDs and ARNs after failed operations and deletion. It excludes full state and secret values. **Cloud absence: unknown** means the retained inventory is not proof of deletion; keep the workspace and finish named-resource checks even when Terraform state is empty.

Jobs run one at a time and show bounded command-status events. Closing or navigating away from the tab does not cancel an operation; returning to Environment reconnects to its status while the server remains running. Browser events omit raw tool output. For a failed operation, keep state and investigate through the terminal and runbook before reviewing a fresh plan. After a server restart, inspect the retained session result and state before retrying. No automatic repair or timed cleanup runs.

The runner accepts only fixed operations for catalog missions and their declared roots. Mutations require the current local process’s capability token and valid Host/Origin checks. It is a local learner tool; it does not accept arbitrary shell commands or filesystem paths.

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
