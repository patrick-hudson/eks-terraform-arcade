# Web workspace

The local workspace guides you through 24 missions: 14 games and ten individual incidents. Its five-stage workflow contains 120 stages, 240 task checkpoints, 72 progressive investigation hints and 24 interview reasoning checks. It reads the same runbooks and code files you can open in your editor.

## Start and stop

Use Python 3.10 or newer on Linux, macOS or WSL2. From the project root:

```bash
python3 web/server.py
```

Open **http://127.0.0.1:8765** and keep that terminal running. No npm installation, AWS credentials or internet connection is needed to use the workspace. External documentation and actual lab commands have their usual internet requirements.

If the port is occupied:

```bash
python3 web/server.py --port 8766
```

Then open http://127.0.0.1:8766. The server accepts only loopback connections. Press Ctrl-C in its terminal to stop it. **Stopping the server leaves any AWS resources you created running.** Finish the mission’s cleanup instructions separately.

## Work through a mission

Choose a lab from the directory, resume your current mission, or use **Surprise me** in the incident gauntlet. Incidents have neutral names so the directory does not disclose their causes. Open one incident at a time on your existing Game 07 cluster.

The sidebar’s **Plain-English glossary** explains unfamiliar terms with practical examples. The questions ask you to make a decision and explain its effect; they do not require memorized definitions.

The **Workspace** view follows five stages:

1. **Brief:** define the delivery contract, prerequisites, cost and cleanup scope.
2. **Build:** follow the complete runbook to create the working copy and reach the initial state. An intended first failure is useful evidence.
3. **Investigate:** record a hypothesis, collect decisive evidence and make the smallest durable change.
4. **Verify:** run the full acceptance sequence and answer the interview reasoning check.
5. **Cleanup:** follow the dependency order, verify deletion and prepare your debrief.

Check each task only after doing it, then select **Record & continue**. You can jump to any stage, including cleanup, at any time. Completing all stages records mission completion. Task checks and evidence are self-reported: the app does not inspect Terraform state, connect to AWS, run commands, grade terminal output or certify teardown.

Use **Open complete runbook here** to read the source without leaving your stage. **Full-screen instructions** opens the **Runbook** view, and **Starter & reference files** opens **Files**. Command cards have copy buttons, but they are checkpoints rather than complete deployment scripts: first run the source’s setup, exports and working-directory commands. Kubernetes repairs edit `candidate.yaml` and go through the workload’s Terraform plan and apply. Diagnostic `kubectl` reads are useful; manual patches and console edits do not count as the repair. The app cannot change your terminal environment.

**Guided** mode opens command checkpoints by default. **Interview** mode initially collapses those details and prompts you to explain your hypothesis before seeking help. You can still open commands, hints and solutions. It is a practice preference, not a locked assessment or automatic score.

The older four-checkpoint session sidebar remains available on Runbook, Files, Hints, Solution and My notes. You can use it to record build/reproduction, explanation, verification and cleanup, then **Mark complete**. These checks share the mission record with the workspace; checking them does not fabricate individual task evidence or five-stage history.

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

The clock measures practice time, not cluster lifetime or AWS charges. Pausing it, completing a mission, deleting a browser record or stopping the server does not stop infrastructure. The $20 figure is the whole curriculum’s planning allowance; the app does not read billing or enforce a cap. Follow [cost and cleanup](cost-and-cleanup.md), including backing-volume verification before foundation teardown.

## Save, export and restore progress

Progress uses schema version 2 under the existing localStorage key `aws-interview-arcade:v1`. The key stays the same so existing version 1 notes and valid completion records migrate automatically. Migration does not invent completed guided stages.

Storage belongs to the browser profile and origin. `localhost` and `127.0.0.1`, different ports, and different browser profiles have separate records. Clearing site data removes progress; private browsing may discard it on close. If browser storage is unavailable or full, the app warns you and retains a temporary in-memory copy. Export before closing.

**Export progress** downloads a JSON backup of notes, evidence, checks and practice state. It records a paused snapshot of each clock at export time; it does not pause the live clock in your current session. **Restore backup** reads a version 1 or 2 JSON file locally, previews how many records can merge, and waits for **Merge backup**. The file is not uploaded. The maximum accepted size is 20 MiB (shown as 20 MB in the interface).

Restore merges complete mission records by update time. A newer record wins; an equal or older backup record leaves the current browser record intact. Unknown mission IDs are skipped. It does not combine conflicting text field by field, so export your current progress before merging valuable alternate notes. Restored clocks are paused and do not accrue the time between export and restore.

Updates from another tab are merged by record timestamp. The app tells you when another tab changes progress; reopen the mission to load its latest details. This is local browser coordination, not account or device sync.

## Local verification

The Python suite covers the source catalog, guided lesson content, hint/answer boundaries and read-only HTTP routes. JavaScript tests cover progress migration, task completion, timers, repeat attempts and backup merging. Node 18+ is used only for development; it is not needed to run the workspace.

```bash
python3 -m unittest discover -s web/tests -p 'test_*.py' -v
node web/tests/core.test.cjs
node web/tests/practice.test.cjs
```

The HTTP tests use temporary fixtures and an ephemeral loopback port. No test provisions AWS infrastructure. See [the validation record](VALIDATION.md) for executed checks and their limitations, and [learning design](learning-design.md) for the teaching contract.

The server exposes approved authored files, fixed learning/toolchain endpoints and an explicit list of web assets. It does not serve directory listings, `run/`, state, plan files, actual tfvars or arbitrary filesystem paths. Vendored Markdown libraries run locally and retain their licenses in `web/vendor/`; see `web/THIRD_PARTY_NOTICES.md` for versions and sources.
