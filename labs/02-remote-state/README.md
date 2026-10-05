# 02 · Two writers, one state

**45–60 minutes · mid-senior · budget $0.10.** Build an S3 backend with native locking, demonstrate contention safely, then retire it without stranding its clients. This game creates one tiny versioned bucket and a Terraform-only checkpoint. There is no DynamoDB table or cloud compute. Charges are tiny S3 storage and requests; the allowance is not a cap. [S3 pricing](https://aws.amazon.com/s3/pricing/).

The mission has two independent Terraform roots. `bootstrap/` keeps its state locally and owns the backend bucket. `workload/` stores its state remotely and owns `terraform_data.checkpoint`. Build the bucket with the same private, versioned, encrypted controls as game 01; export `bucket_name`. Use lab-only `force_destroy = true` because every stored state version must be deleted during retirement. Never use this bucket for any other project.

In the workload root, create a `terraform_data.checkpoint` with constant input and a creation-time `local-exec` provisioner running `sleep 45`. Export `checkpoint_id`. The bounded local delay holds the backend lock so you can observe contention; it is a demonstration technique, not an application deployment pattern. Keep `backend "s3" {}` partial: backend arguments are supplied during init, before normal Terraform variable evaluation.

Explain why backend and AWS provider authentication are separate, which lock-file permissions matter, what locking does not protect, and why destroying backend infrastructure first is dangerous. Layered [HINTS.md](HINTS.md) and [ANSWERS.md](ANSWERS.md) are separate.

From the extracted package directory:

```bash
export LAB_ROOT="$(pwd)"
test -d "$LAB_ROOT/labs/02-remote-state"
: "${TF_VAR_expected_account_id:?Set the intended dedicated lab account ID first}"
export AWS_REGION="${TF_VAR_region:-us-west-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_VAR_region="$AWS_REGION"
test "$(aws sts get-caller-identity --query Account --output text)" = "$TF_VAR_expected_account_id"
mkdir -p "$LAB_ROOT/run/02-remote-state/"{bootstrap,workload}
cp "$LAB_ROOT/labs/02-remote-state/starter/bootstrap/"*.tf "$LAB_ROOT/run/02-remote-state/bootstrap/"
cp "$LAB_ROOT/labs/02-remote-state/solution/bootstrap/.terraform.lock.hcl" "$LAB_ROOT/run/02-remote-state/bootstrap/"
cp "$LAB_ROOT/labs/02-remote-state/starter/workload/"*.tf "$LAB_ROOT/run/02-remote-state/workload/"
cp "$LAB_ROOT/labs/02-remote-state/solution/workload/.terraform.lock.hcl" "$LAB_ROOT/run/02-remote-state/workload/"
cd "$LAB_ROOT/run/02-remote-state/bootstrap"
${EDITOR:-vi} main.tf
terraform init
terraform fmt
terraform validate
terraform plan -out=bootstrap.tfplan
terraform apply bootstrap.tfplan
export STATE_BUCKET="$(terraform output -raw bucket_name)"
```

Keep this terminal's exported variables. Bootstrap state stays local throughout the mission. Build and initialize the workload:

```bash
cd "$LAB_ROOT/run/02-remote-state/workload"
${EDITOR:-vi} main.tf
cat > backend.hcl <<EOF
bucket              = "${STATE_BUCKET}"
key                 = "workload/terraform.tfstate"
region              = "${AWS_REGION}"
encrypt             = true
use_lockfile        = true
allowed_account_ids = ["${TF_VAR_expected_account_id}"]
EOF
terraform init -backend-config=backend.hcl
terraform fmt
terraform validate
terraform plan -out=workload.tfplan
terraform apply workload.tfplan
# The 45-second delay is intentional and runs on your laptop.
aws s3api head-object --bucket "$STATE_BUCKET" --key workload/terraform.tfstate
terraform state list
# Required: terraform_data.checkpoint appears.
```

Run two Terraform processes against the same backend. The second should fail to acquire the lock; this is the protection you are testing. Do not use `-lock=false` or manually delete a lock.

```bash
terraform apply -replace=terraform_data.checkpoint -auto-approve > holder.log 2>&1 &
HOLDER_PID=$!
LOCK_SEEN=false
for attempt in $(seq 1 30); do
  if aws s3api head-object --bucket "$STATE_BUCKET" --key workload/terraform.tfstate.tflock >/dev/null 2>&1; then
    LOCK_SEEN=true
    break
  fi
  sleep 1
done
if [ "$LOCK_SEEN" = true ]; then
  if terraform plan -lock-timeout=3s > contender.log 2>&1; then
    LOCK_RESULT=unexpected_success
  else
    LOCK_RESULT=expected_failure
  fi
  cat contender.log
else
  LOCK_RESULT=no_lock_observed
  printf 'No lock observed; inspect holder.log and rerun this section.\n'
fi
wait "$HOLDER_PID"
cat holder.log
test "$LOCK_RESULT" = expected_failure
grep -F 'Error acquiring the state lock' contender.log
terraform plan -lock-timeout=10s -detailed-exitcode
# Required: contention specifically failed on locking, holder succeeded,
# and this final plan returns 0 after the holder releases the lock.
```

The narrowly scoped `-auto-approve` above replaces only a local `terraform_data` instance in this game. Do not generalize it to unreviewed cloud plans. If lock observation failed, keep the bucket and inspect the logs before retrying. A credential error is not a passing lock test.

**Teardown order is part of the grade.** First destroy the workload using its remote state. Then migrate its now-empty state back to an explicit local backend. Only then destroy the bootstrap bucket:

```bash
cd "$LAB_ROOT/run/02-remote-state/workload"
# Ensure the holder process has finished before this section.
terraform plan -destroy -out=destroy-workload.tfplan
terraform apply destroy-workload.tfplan
terraform state pull > destroyed-state-backup.json
mv backend.tf backend.s3.tf.disabled
cat > backend.tf <<'EOF'
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
EOF
terraform init -migrate-state -force-copy
terraform show -json | jq -e '[.values.root_module.resources[]? | select(.mode == "managed")] | length == 0'
jq -e '.backend.type == "local"' .terraform/terraform.tfstate
cd "$LAB_ROOT/run/02-remote-state/bootstrap"
export STATE_BUCKET="$(terraform output -raw bucket_name)"
terraform plan -destroy -out=destroy-backend.tfplan
terraform apply destroy-backend.tfplan
aws s3api wait bucket-not-exists --bucket "$STATE_BUCKET"
terraform show -json | jq -e '[.values.root_module.resources[]? | select(.mode == "managed")] | length == 0'
```

Here `-force-copy` accepts the state migration into this dedicated local file; it does not disable locking. Preserve the pulled backup and local state until the checks succeed. The bucket's old state versions are removed by lab-only `force_destroy`. Do not replace migration with `terraform init -reconfigure`: that forgets previous backend configuration without copying its state.

Recovery: if the workload was never initialized/applied, it owns nothing; destroy bootstrap directly. If its configuration is invalid after an apply, restore the matching `solution/workload/main.tf` and keep its active backend configuration, then execute cleanup above. If it is already migrated locally, do not repeat the migration; verify local state is empty and destroy bootstrap. If the bucket name output is unavailable after a partial bootstrap apply, read `terraform state show aws_s3_bucket.lab`. Never delete bootstrap state to “fix” a backend problem.

References: [S3 backend and locking permissions](https://developer.hashicorp.com/terraform/language/backend/s3), [terraform init and migration](https://developer.hashicorp.com/terraform/cli/commands/init), [state locking](https://developer.hashicorp.com/terraform/language/state/locking).
