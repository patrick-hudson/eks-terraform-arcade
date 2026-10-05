# 06 — Rescue state without recreating infrastructure

**45 minutes · import, drift, refresh-only, moved blocks · negligible cost with no log ingestion.** This deliberately creates one disposable log group outside Terraform. A small helper records successful creation before setting retention. That receipt is required for import, fault injection and cleanup in a shared account.

## Incident A: inherit an existing resource

The log group exists, but this Terraform workspace does not yet know it owns that group. Your first plan looks like a create. Diagnose before applying.

```bash
(
  set -euo pipefail
  mkdir -p "$LAB_ROOT/run/06-state-rescue"
  cp "$LAB_ROOT/labs/06-state-rescue/solution/"*.tf "$LAB_ROOT/run/06-state-rescue/"
  cp "$LAB_ROOT/labs/06-state-rescue/solution/.terraform.lock.hcl" "$LAB_ROOT/run/06-state-rescue/"
  cd "$LAB_ROOT/run/06-state-rescue"
  python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" create &&
  terraform init -lockfile=readonly &&
  terraform plan
)
```

Before running this block, export `AWS_PROFILE`, `TF_VAR_expected_account_id`, `TF_VAR_region` and a distinctive `TF_VAR_lab_id`. The helper sends every AWS request to that exact profile and region, and verifies the account. If the name already exists, it stops without changing retention or writing an ownership receipt. Choose a different lab ID; a matching name or matching tags alone do not prove the group is yours. Do not create a receipt by hand or substitute an old `resource-name.txt` file.

Keep `state-rescue-fixture.json` with this workspace. If creation succeeds but retention setup fails, the receipt remains: fix the access error, then follow the guarded import and Terraform reconciliation in the answer. Running `create` again never overwrites a receipt. A failed or timed-out create with no receipt needs investigation; it is not permission to import an existing name.

Applying that create would fail with `ResourceAlreadyExistsException`; run it once if you want to see the failure, then recover. Adopt it into state without deleting or recreating the log group. Use `import` or an import block; explain the choice. See [hints](HINTS.md) before the [answer](ANSWERS.md).

## Incident B: drift

After adoption and a clean plan, deliberately change the test log group's retention outside Terraform. This is fault injection: it imitates a change made by another operator. The repair must go through Terraform.

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" drift &&
  terraform plan -refresh-only &&
  terraform plan
)
```

Compare the two plans. Which one changes only recorded state and which one proposes changing AWS? Write your explanation before repairing drift. Acceptance: configured and actual retention return to one day, without resource replacement.

## Incident C: a risky refactor

Rename the resource address from `aws_cloudwatch_log_group.app` to `aws_cloudwatch_log_group.service`. Before applying, inspect whether Terraform proposes destruction/recreation. Make the rename a state-address move; the remote resource must keep its identity and data. `refactor/main.tf` contains the reference answer, so do not open it yet.

Acceptance: the plan shows a move and **zero add/change/destroy**, then a clean follow-up plan; the original log group remains. What would change if the resource lived in another state/backend? Why is `state rm` not cleanup?

## Teardown — even if import never succeeded

If the resource is managed, use the exact working directory containing its state:

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  terraform state list
  if python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" check --state; then
    terraform plan -destroy -out=destroy.tfplan &&
    terraform show destroy.tfplan &&
    read -r -p 'Review the plan. Type destroy to apply it: ' CONFIRM &&
    test "$CONFIRM" = destroy &&
    terraform apply destroy.tfplan &&
    python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" absent
  fi
)
```

The guard checks the receipt, current AWS account, exact name, ownership tags, and Terraform state. State must contain only this group's original or refactored address, with the matching account and region. Review the shown plan before typing `destroy`. A failed guard never runs the plan or apply commands.

If import has **not** succeeded and state is empty, first bring the exact recorded fixture under Terraform ownership using this block. If import fails, keep the receipt and resolve the error before continuing; an empty state does not mean the log group is gone.

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  if LOG_GROUP="$(python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" name)"; then
    terraform init -lockfile=readonly &&
    terraform import aws_cloudwatch_log_group.app "$LOG_GROUP"
  fi
)
```

Then run the guarded teardown block above. `absent` must confirm the exact group is gone. Preserve the receipt and state/backup files until verification completes. No manual AWS deletion, bulk deletion or state-file editing.

For another session, first verify absence, then move the entire finished `run/06-state-rescue` directory into a dated folder under `run/archive/` and run `arcade start 06` again. That archive stays excluded from Git. Keep the old receipt and state as evidence; never reuse that receipt to claim ownership of another group.

Sources: [import](https://developer.hashicorp.com/terraform/language/import), [refresh-only](https://developer.hashicorp.com/terraform/tutorials/state/refresh), [moved blocks](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring).
