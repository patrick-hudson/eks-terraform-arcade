# Answers — 06

## A: import the exact existing log group

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  if LOG_GROUP="$(python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" name)"; then
    terraform init -lockfile=readonly &&
    terraform import aws_cloudwatch_log_group.app "$LOG_GROUP" &&
    terraform plan -out=reconcile.tfplan &&
    terraform show reconcile.tfplan &&
    terraform apply reconcile.tfplan &&
    terraform plan
  fi
)
```

The helper prints the name only after matching the creation receipt, profile, region, account and live ownership tags. A name collision or missing receipt cannot pass this guard. Reconciliation can align tags and retention; inspect it first. An import block is a reviewable alternative, but use the same ownership check before planning and applying it. Do not use both import methods for the same address. Importing does not automatically prove your configuration matches AWS.

## B: revert the controlled drift

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  if python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" check --state; then
    terraform plan -out=repair.tfplan &&
    terraform show repair.tfplan &&
    terraform apply repair.tfplan
  fi
)
```

A normal plan refreshes remote values before comparing them with configuration, then proposes 7→1 days. Applying refresh-only would persist the observed 7-day retention in state while HCL still says 1; the next normal plan would still propose restoring 1. To accept drift permanently, intentionally change HCL too.

## C: record the move

```bash
(
  set -euo pipefail
  cd "$LAB_ROOT/run/06-state-rescue"
  if python3 "$LAB_ROOT/labs/06-state-rescue/fixture.py" check --state; then
    cp "$LAB_ROOT/labs/06-state-rescue/refactor/main.tf" main.tf &&
    terraform plan -out=move.tfplan &&
    terraform show move.tfplan &&
    terraform apply move.tfplan &&
    terraform state list &&
    terraform plan
  fi
)
```

The moved block changes the address without a recreate. Keep it for consumers that may still upgrade from the previous module version. An imperative `terraform state mv` can also repair an address, but does not carry that migration as shared configuration.

For cross-state migrations, coordinate exclusive ownership, lock both workflows, preserve backups, establish destination configuration and imports, and ensure the original no longer manages the object. A resource must not be actively managed by two independent states. `state rm` only forgets; it does not delete AWS resources or stop charges.
