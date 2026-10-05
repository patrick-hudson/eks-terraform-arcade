# Hints · bootstrap, lock, retire

**Foundation:** A backend stores Terraform's record of resource identities. A provider talks to resource APIs. Backend initialization occurs before the normal resource graph and cannot depend on resources that the same root has yet to create.

<details><summary>Hint 1 — separate the roots</summary>

Bootstrap creates the bucket with local state. Workload points its S3 backend at the resulting name. Keep the bootstrap state somewhere recoverable until the bucket is deleted; do not move it into its own bucket for this exercise.
</details>

<details><summary>Hint 2 — native locking</summary>

Set `use_lockfile = true` in backend configuration. Terraform writes a sibling object with `.tflock` appended to the state key. S3 permissions must permit reading, creating and deleting this lock object. Current S3 backend documentation deprecates DynamoDB locking.
</details>

<details><summary>Hint 3 — read the actual error</summary>

An authentication failure or an invalid Terraform expression is not lock contention. Inspect the second process's error and verify that the first process was still active. The plan should succeed after that process releases its lock.
</details>

<details><summary>Hint 4 — safe retirement</summary>

Deleting cloud resources does not remove the need to read their Terraform state. Destroy the dependent workload first, migrate its backend to local, then destroy storage. If a backend has other consumers, all of them need to be handled before it can be retired.
</details>
