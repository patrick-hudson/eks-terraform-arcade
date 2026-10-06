# Read a Terraform plan locally

The plan coach explains proposed operations without printing resource values. It
does not run Terraform, contact AWS, write a copy of your input, approve an apply,
or verify ownership, live behavior or price. Python is the only requirement for
reading an existing JSON plan.

From the kit root:

```bash
./arcade review-plan /path/to/plan.json
./arcade review-plan /path/to/plan.json --json
```

The direct entry point is also available:

```bash
python3 scripts/review-plan.py /path/to/plan.json
```

Use the saved plan from your mission's existing review process. To read it
without creating an intermediate JSON file, run from that Terraform workspace:

```bash
terraform show -json reviewed.tfplan | "$LAB_ROOT/arcade" review-plan -
```

`terraform show -json` can expose sensitive values in its raw output. Keep saved
plans and any JSON files private. The coach reads them locally in memory and
constructs a new summary from selected metadata; it does not sanitize and repeat
the original document. Do not paste raw plan JSON into the browser practice
surface. There is no plan-upload endpoint.

## What the summary means

| Observation | Interpretation |
| --- | --- |
| `create`, `read`, `update`, `delete`, `no-op` | Distinct proposed actions. A read normally fetches a data source; a no-op can still carry a move or import marker. |
| `delete`, then `create` | Replace the old object by deleting it first. Consider the resulting interruption. |
| `create`, then `delete` | Create the replacement first. Capacity, application readiness and handover remain separate questions. |
| `previous_address` | Terraform records an address move. Inspect the actions too: a move can accompany an update or replacement. |
| Import marker | An existing object is being imported. The import ID is omitted; the marker does not establish ownership. |
| `resource_drift` | Differences observed during refresh relative to prior saved state. These are separate from proposed actions. |
| Unknown values | Some resulting values cannot be determined yet. Unknown does not mean empty, absent or necessarily wrong. |
| Deferred changes or `complete=false` | The current plan does not describe all work needed to converge. Later actions may differ. |
| Missing flags | Completeness, applicability or planning-error status is unknown; absence is never treated as success. |

Action counts count each recognized action: two replacements contribute two
creates and two deletes. Resource counts count distinct addresses. Object-change
counts also include deposed objects that can share an address. Each of the
proposed-change, drift and deferred sections has its own counts. Deferred actions
are tentative and never added to the proposed-change totals. Unsupported action
sequences are counted separately, with their input tokens omitted; they do not
become no-ops.

The human and JSON summaries omit before/after values, variables, output names
and values, import IDs, sensitivity-mask contents, replacement paths and arbitrary
diagnostics. Quoted instance selectors are displayed as `["<redacted>"]`, including
selectors within module addresses. Numeric selectors remain visible. Control
characters are replaced. Resource and module labels outside selectors remain
visible, so treat the summary as project metadata even though values are omitted.

## Input and output contract

The command accepts one UTF-8 JSON object from `terraform show -json` for a saved
plan. State-only JSON and `terraform plan -json` streaming events are different
formats and are rejected. Format major version 1 is supported; unknown additive
fields in a version-1 document are ignored. A malformed shape, unsupported major
version or unreadable file returns exit code 2 with a concise error that does not
repeat the input. Successful interpretation returns 0, including when uncertainty
or unsupported actions are reported. Exit code 0 is not permission to apply.

Input is capped at 10 MiB and 10,000 resource records across proposed changes,
drift and deferrals. Each section includes at most 100 detail rows in both output
formats; totals and uncertainty counts include every record. JSON reports use
`schemaVersion: 1`, `evidenceKind: "local-plan-interpretation"`, separate `changes`,
`drift` and `deferred` summaries, `metadata`, `uncertainties` and `limitations`.
Errors with `--json` are objects containing `status: "error"` and `message`.

For Python callers, `scripts/plan_review.py` provides `read_plan(stream)` to read
bounded JSON, `review_plan(document)` to construct the report,
`format_review(report)` for human output and `main(argv=None)` for command dispatch.
`PlanReviewError` contains a value-free explanation. No learner plan is accepted
by the browser or the authored drill engine.

## Practice and evidence

The Practice desk and `arcade drill` include three **authored simulations**:

- `plan-replacement-order`: compare replacement order with availability needs.
- `plan-address-change`: distinguish a rename from a recorded move.
- `plan-incomplete-evidence`: separate drift, unknowns and deferred work from
  proposed actions and runtime recovery.

Their excerpts are teaching material. They were not captured from AWS and their
feedback cannot prove live health, cleanup or mastery. Follow the linked mission
for Terraform-owned repairs, scoped live verification and cleanup. Existing shared
account boundaries, the $20 total allowance and the us-west-2 preference still
apply to any later authorized cloud work.

The developer proof uses genuine locally generated plans:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_plan_review.py -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/tests/verify_plan_review_terraform.py
```

The second command requires Terraform (`.tools/bin/terraform` is preferred, then
PATH). It creates a temporary local workspace, uses only built-in `terraform_data`
resources and an environment without cloud credentials, and removes its plans
and state on exit. It verifies create, update, both replacement orders, a plain
rename and a recorded move. This proves those Terraform JSON shapes agree with
the reader; it is not an AWS test. Unit tests separately exercise synthetic drift,
imports, deferrals, malformed input and secret omission.

Semantics follow HashiCorp's [Terraform JSON format](https://developer.hashicorp.com/terraform/internals/json-format).
HashiCorp's [show command documentation](https://developer.hashicorp.com/terraform/cli/commands/show)
explains the sensitivity of raw JSON output.
