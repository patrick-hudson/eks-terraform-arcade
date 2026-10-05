# Answer · lock ownership is operational state

The complete roots are `solution/bootstrap` and `solution/workload`. Before their respective initializations, install the main files in the same working directories:

```bash
: "${LAB_ROOT:?Set LAB_ROOT to the extracted package directory}"
cp "$LAB_ROOT/labs/02-remote-state/solution/bootstrap/main.tf" "$LAB_ROOT/run/02-remote-state/bootstrap/main.tf"
cp "$LAB_ROOT/labs/02-remote-state/solution/workload/main.tf" "$LAB_ROOT/run/02-remote-state/workload/main.tf"
```

Then follow the mission's bootstrap, backend configuration, locking and cleanup commands. Do not copy backend configuration over a working root during cleanup: its current backend determines where Terraform reads its state.

The workload is intentionally small:

```hcl
resource "terraform_data" "checkpoint" {
  input = "remote-state-locking-exercise"
  provisioner "local-exec" {
    command = "sleep 45"
  }
}
```

The first apply creates it. The later `-replace` recreates it and reruns the delay while holding the lock. Another locking plan cannot enter during that period. This is mutual exclusion for clients using the same state key; it is not a global lock across every state in the bucket and does not stop someone changing AWS resources directly.

The backend configuration explicitly enables native locking and independently checks the allowed AWS account. The relevant S3 permissions are bucket listing, get/put for state, and get/put/delete for the lock object. Backend and provider credentials can differ; configuring one does not implicitly configure the other. [S3 backend reference](https://developer.hashicorp.com/terraform/language/backend/s3).

The deliberate contention should report an acquiring-state-lock error, including lock owner information. Once the holder exits, an ordinary plan should work. `force-unlock` is reserved for a confirmed abandoned lock after proving no process still owns it. Using it against a running apply risks state corruption.

For retirement, the workload is destroyed while S3 still exists. Replacing its backend block with a local backend and running `init -migrate-state` copies the final empty state back. The `.terraform/terraform.tfstate` check verifies backend metadata; it is distinct from the real workload state now stored in `terraform.tfstate`. Finally, deleting bootstrap removes the bucket and all state versions. Keeping the bootstrap root local avoids a circular teardown dependency.

State can contain sensitive values even when outputs are redacted. This exercise uses no secrets. A production answer should discuss recovery, state access boundaries, version restoration and deletion approval; the disposable lab's `force_destroy` is not a production recommendation.
