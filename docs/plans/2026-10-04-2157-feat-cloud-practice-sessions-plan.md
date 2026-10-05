---
title: Cloud Practice Sessions - Plan
type: feat
date: 2026-10-04
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---
# Cloud Practice Sessions - Plan

## Goal Capsule

- **Objective:** Learners can work through a real AWS break/fix exercise from either interface, see whether their repair works, and finish with a clear cleanup result.
- **Means:** Shared local session operations with two clients (KTD1), extending the existing registered workspaces.
- **Authority:** The user's AWS budget and ownership constraints, then Product Contract requirements, then technical decisions and units.
- **Execution:** Parallel implementation with a coordinating agent responsible for integration, live verification, cleanup and release.
- **Stop conditions:** Stop cloud creation when projected testing exceeds $3, identity differs from the intended sandbox, or ownership cannot be established. Preserve state and report exact remaining resources on cleanup failure.
- **Landing:** Update the feature branch, publish a reviewed PR and wait for CI. Do not merge.

---
## Product Contract

### Summary

Add a session workbench shared by the browser, CLI and TUI. It guides prerequisites and Terraform operations, preserves verification evidence, displays running-cost estimates, and makes cleanup visible. Refine both interfaces with restrained purple accents and readable dark themes.

### Problem Frame

The current browser teaches and prints commands while the TUI executes a subset of missions. Verification and runtime state are separate, so learners must infer their next step and whether a successful apply actually repaired anything. This interrupts practice and makes it too easy to leave billable environments running.

### Key Decisions

- **Both interfaces operate the same local workspaces.** Governs R1, R2. The user explicitly requested feature parity and cloud provisioning instead of a local-only TUI.
- **Repairs remain in Terraform.** Governs R3. (session-settled: user-directed — chosen over manual console changes: practice must teach durable infrastructure repair.)
- **Cloud testing is small and temporary.** Governs R7. (session-settled: user-directed — chosen over broad deployment testing: this account contains unrelated resources and testing must cost only a few dollars.)

### Requirements

**Session workflow**

- R1. Web, CLI and TUI expose the same mission catalog, runtime capabilities, prerequisites, cost estimates and session results.
- R2. Learners can prepare, configure, plan, approve a saved plan, inspect verification, and plan/apply cleanup from either interface for runtime-supported missions; every remaining recipe has its complete ordered runbook available in both clients.
- R3. Submit repair checks behavior without changing the deployed infrastructure and labels incomplete or stale evidence clearly; it must never treat an apply alone as a passed exercise.
- R4. Every mission displays environment prerequisites before provisioning, with a direct route to the prerequisite and reverse cleanup ordering.
- R5. Sessions retain a metadata-only resource inventory and the latest operation result so a failed command does not erase cleanup context.

**Learning and interface**

- R6. The browser offers system, light and dark themes, while the TUI offers an intentional dark/purple layout, clear keyboard help, catalog search, and contextual actions without hiding cloud missions.
- R8. Show estimated 1-hour and 2-hour costs, explaining shared EKS charges and activity-based costs without promising a billing cap.
- R9. Preserve existing browser progress, authored drills, workspace edits and state. Record repair checks separately from self-reported completion.
- R10. Explain uncommon terms in context and keep hints progressive; new incident content should vary the cause rather than repeat the same answer.

**Cloud proof and release**

- R7. Live tests use us-west-2 and the explicitly confirmed sandbox account, create only uniquely owned resources, inventory their identifiers/ARNs, and verify cleanup. This testing pass has a $3 maximum expected cost and a target below $0.65.
- R11. Verify the current supported EKS/toolchain versions from official sources, and prove one short serverless exercise plus one EKS incident where permissions and the budget allow.
- R12. README setup instructions and actual UI/TUI captures describe the delivered controls and distinguish local tests from live cloud evidence.

### Acceptance Examples

- AE1. Covers R1, R2, R4: A learner opens an EKS image-pull incident without a foundation; both clients show the missing foundation and a route to prepare it before the incident can apply.
- AE2. Covers R2, R5: After reviewing a plan, the learner edits Terraform; both clients reject applying the stale saved plan and retain cleanup information.
- AE3. Covers R3, R9: Pods exist but the service is broken; submission reports the failed behavioral check rather than marking the exercise complete.
- AE4. Covers R5, R7: Apply fails after creating resources; the inventory and state remain available, cleanup uses that exact workspace, and the result never claims absence from empty state alone.
- AE5. Covers R6, R9: Changing theme and reloading preserves the theme and existing study progress; keyboard navigation remains visible at narrow widths.

### Scope Boundaries

This increment covers a local application, not a hosted multi-user service. No arbitrary browser shell endpoint, account-wide deletion, credential upload or automatic repair is added. Automatic deletion on a timer is not built: it can destroy a learner's active work, while explicit cleanup with retained inventory fits the workflow. A future opt-in expiring sandbox would require an independently owned cloud account or stronger ownership isolation.

### Deferred to Follow-Up Work

Add more paid architectures after the shared workflow has live evidence. Add spaced repetition and same-symptom challenge variants after repair submissions can distinguish a real result from self-reported progress.

---
## Planning Contract

### Key Technical Decisions

- KTD1. **One session service over the current runtime.** Reuse `lab_runtime.Runtime`, `lab_manager` recipes and the bounded verifier rather than create a second provisioning implementation. A small shared service returns capabilities, phase, suggested action, estimates, metadata inventory and verification receipt. This gives R1 a single source of truth.
- KTD2. **An explicitly enabled loopback runner.** Keep ordinary `arcade serve` read-only; `arcade serve --runner` enables fixed operations for the local learner. Retain Host/Origin checks, require a per-process capability on mutations, reject arbitrary paths/argv, and serialize operations. Saved-plan approval remains explicit and bound to the current receipt under R2/R7. This is a new opt-in capability, not an externally hosted API.
- KTD3. **Bounded asynchronous jobs for the browser.** Run one selected operation per session through fixed Python calls. Return job IDs, bounded logs and final status; do not tie Terraform lifetime to the browser request. A disconnected tab leaves the state and operation visible for recovery under R5.
- KTD4. **Root-aware operations for multi-root labs.** Extend runtime support for Games09,10,13 with explicit root selection and prerequisite/output wiring. Never evaluate recipe shell text. Games02/06 and the capstone retain their deliberately instructional state-migration/runbook steps, presented with parity under R2.
- KTD5. **Evidence is scoped, dated and invalidated by source changes.** Connect existing verification checks to submission, include failed and unknown checks, and compare source fingerprints before calling a prior receipt current. Game00 uses its actual Terraform contract; cloud checks state what they observed under R3.
- KTD6. **Metadata-only local inventory.** Extract managed addresses, types, IDs and ARNs from Terraform observations after operations, preserving prior records on failure or destroy. Never expose full state or secrets to the browser. Distinguish Terraform destruction from verified cloud absence under R5.
- KTD7. **Use the existing frontend and curses implementation.** Add semantic theme tokens and a focused session panel; keep ordinary learning navigation and progressive disclosure. Avoid a framework migration during R6.
- KTD8. **Shared estimates, not invented billing precision.** Use an authored pricing model for the existing architecture, display dated assumptions and incremental versus shared costs, and retain request/storage uncertainty under R8. Base EKS estimate includes one t3.medium, standard-support control plane,20GiB gp3 and one public IPv4.

### High-Level Technical Design

The client boundary has three paths into the same operations:

| Caller | Boundary | Execution | Shared result |
|---|---|---|---|
| CLI | Explicit command and arguments | Session service to runtime/verifier | Local receipt |
| TUI | Selected action and typed confirmation | Session service to runtime/verifier | Local receipt |
| Browser | Loopback capability and fixed operation | Job coordinator to session service | Local receipt and bounded job status |

The operation protocol is prepare, configure, plan, review, approve, then inspect result. Approval compares the saved plan with current inputs and state before any apply. Source editing returns the session to planning rather than reusing approval. Destroy follows the same protocol with a separate plan and then absence checks.

| Session state | Next useful action | Meaning |
|---|---|---|
| No workspace | Prepare | Nothing deployed by this session |
| Prepared | Configure or inspect prerequisites | Files alone do not prove readiness |
| Planned | Review and explicitly approve | Plan is bound to current source/state |
| Applied or failed apply | Diagnose or submit repair | Resources may exist and incur charges |
| Verified repair | Review cleanup plan | Receipt describes specific checks |
| Destroyed | Confirm absence | Empty Terraform state is not cloud absence |

Metadata flows from recipe and registered workspace to the shared service, then to either client's projection. Full Terraform state remains local to the runtime. Behavioral API observations become bounded verification receipts. Pricing takes authored assumptions and session time, never an AWS billing promise.

### Assumptions

The session-workbench design is an agent-selected product bet from the ranked ideation document. The learner runs a trusted checkout locally. Shell files and Terraform that the learner edits are already executable content; the browser runner must not widen that trust to arbitrary remote requests. Exact multi-root wiring and new verifier coverage will be resolved against each recipe during implementation.

### Risks and Dependencies

Cloud IAM propagation, managed-runtime startup and EKS provisioning can fail despite local checks. Capture enough evidence before unconditional cleanup to diagnose failures. EKS can create service-linked roles and EC2/network child resources outside the visible Terraform graph; the test harness must inventory only newly created objects and delete only those it owns. Keep the EKS test late in implementation to avoid idle spend.

---
## Implementation Units

### U1. Shared cloud-session operations

**Goal:** Provide a reusable session API for all clients.

**Requirements:** R1–R5, R8, R9; KTD1, KTD4–KTD6, KTD8.

**Dependencies:** Existing practice-desk implementation and review fixes.

**Files:** `scripts/lab_runtime.py`, `scripts/lab_session.py`, `scripts/arcade`, `scripts/tests/test_lab_runtime.py`, `scripts/tests/test_lab_session.py`, `lab-recipes.json`.

**Approach:** Wrap the existing guarded runtime; add status, explicit root selection, costs, metadata inventory and repair receipts. Connect bounded verification for supported labs and name unsupported behavioral checks. Extend multi-root provisioning without running documented shell strings.

**Patterns:** Existing workspace registration, fixed argv, saved-plan receipts and verifier checks.

**Test scenarios:**
- A stale plan is refused after source, state or account changes.
- A multi-root mission blocks a workload until its infrastructure outputs exist and prevents foundation deletion with dependents.
- Failed apply and destroy retain prior inventory; absence remains unknown without an API check.
- Submission records failure or unknown results and marks old results stale after edits.

**Verification:** CLI operations and fake-runner integration tests share the same status as TUI/web projections; real local Terraform lifecycle passes.

### U2. Browser session workbench and dark design

**Goal:** Make cloud sessions usable from the browser without losing the study interface.

**Requirements:** R1–R6, R8, R9; KTD2, KTD3, KTD7.

**Dependencies:** U1 service contract; visual changes can begin independently.

**Files:** `web/server.py`, `web/session.py`, `web/session.js`, `web/app.js`, `web/index.html`, `web/styles.css`, `web/workspace.css`, `web/tests/test_server.py`, `web/tests/session.test.cjs`, `web/tests/theme.test.cjs`.

**Approach:** Add an opt-in fixed-operation API and session panel with prerequisites, estimates, current job, plan review, approval and submission. Add persistent system/light/dark themes through semantic tokens. Keep logs bounded and sensitive files outside the file API.

**Test scenarios:**
- Read-only mode rejects every runtime mutation.
- Wrong Host, Origin, token, path or operation is rejected before execution.
- Double submission cannot run concurrent applies; a page reload recovers the running job.
- Theme changes preserve progress and all controls remain keyboard-accessible at mobile width.

**Verification:** HTTP integration tests plus actual browser create/plan/apply/submit/destroy on Game00, dark/light screenshots, narrow-layout inspection and no console errors.

### U3. TUI mission control

**Goal:** Make the terminal a complete, deliberate interface to the same cloud sessions.

**Requirements:** R1–R6, R8, R9; KTD1, KTD7.

**Dependencies:** U1 service contract; layout and search can begin independently.

**Files:** `scripts/arcade_tui.py`, `scripts/tests/test_tui.py`, `scripts/tests/test_tui_pty.py`.

**Approach:** Add catalog search, clearer groups and next actions, shared cost/status/repair results, root selection, full runbook access and visible cleanup actions. Improve spacing, contrast and help without hiding cloud missions behind offline practice.

**Test scenarios:**
- Search finds an AWS mission by title or symptom and preserves navigation on return.
- Selecting a prerequisite or multi-root operation targets the correct registered workspace.
- External errors, interrupts and terminal resizes restore usable curses navigation.
- TUI and browser receive identical mission capabilities and session receipts.

**Verification:** Real PTY tests, a captured cloud-mission workflow and readable screenshots at supported sizes.

### U4. Live cloud proof and current versions

**Goal:** Prove the core cloud lessons on AWS within the test allowance.

**Requirements:** R7, R10, R11; KTD5, KTD6.

**Dependencies:** U1 for EKS lifecycle; independent serverless diagnosis can start earlier.

**Files:** `scripts/smoke_aws.py`, `scripts/tests/test_smoke_aws.py`, `labs/05-serverless-counter/`, `toolchain.json`, affected EKS pins and docs, `docs/VALIDATION.md`.

**Approach:** Diagnose the observed repaired-Lambda timeout with bounded instrumentation before changing the authored lesson. Update current supported version pins from official sources. Run one uniquely named EKS foundation and a Terraform-repaired image fault, optionally the existing public-access lesson within the same short session. Preserve exact creation inventory and deletion evidence in ignored run artifacts.

**Test scenarios:**
- Expected broken Lambda fails for the intended reason and repaired counter increments twice.
- The EKS workload reaches the authored broken state, then becomes ready after Terraform repair.
- Cleanup runs on both success and failure and verifies exact owned resources absent.
- Pricing/runtime changes are reflected in plan allowlists and tests rather than bypassing validation.

**Verification:** Real AWS receipts with timestamps, ARNs/IDs, observed failures, successful checks and cleanup evidence; estimated spend reported separately from billing.

### U5. Integrated release and documentation

**Goal:** Ship a coherent product with honest setup and verification evidence.

**Requirements:** R1, R9, R12.

**Dependencies:** U1–U4.

**Files:** `README.md`, `docs/images/`, `docs/VALIDATION.md`, `scripts/package-kit.py`, release archive and manifest.

**Approach:** Document the opt-in runner, TUI controls, prerequisite flow, price assumptions and cleanup. Capture the actual interfaces and rebuild the portable kit. Review cross-client contracts and run focused browser/PTY tests before the full suite and CI.

**Test scenarios:**
- Fresh extraction runs the documented launcher commands from a path containing spaces.
- Existing progress/state survive the update.
- The packaged app contains all new assets and modules.

**Verification:** Passing local suites, browser/PTY evidence, clean package manifest, reviewed PR and resolved CI.

---
## Verification Contract

Run the existing Python suites under `scripts/tests` and `web/tests`, plus `node --test web/tests/*.test.cjs`. Run `scripts/tests/verify_plan_review_terraform.py`, actual Game00 lifecycle and the package extraction smoke. Use actual browser and PTY interaction for U2/U3 rather than only markup assertions. Live U4 evidence must include cleanup even if the exercise fails. Cloud resources must not remain idle while release documentation is written.

---
## Definition of Done

All units satisfy their verification outcomes. The two clients expose the same supported session operations and make manual runbook coverage explicit. The delivered dark/light designs are visually checked, the README contains actual captures, and the release kit runs from a clean extraction. No abandoned implementation remains. Every created AWS resource is deleted with evidence, or explicitly reported with its ARN/ID and exact recovery command before the work can stop. The final report separates verified cloud behavior, local tests, estimates and residual limitations.
