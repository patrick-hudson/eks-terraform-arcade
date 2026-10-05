# Hints · private storage

**Foundation:** A bucket is a namespace with separate configuration APIs. The provider models versioning, ownership, encryption and public access controls as separate resources. References to the bucket ID create dependency edges automatically.

<details><summary>Hint 1 — split the controls</summary>

Write the bucket first. Then use its ID in `aws_s3_bucket_public_access_block`, `aws_s3_bucket_ownership_controls`, `aws_s3_bucket_versioning`, and `aws_s3_bucket_server_side_encryption_configuration`. All four public access flags must be true.
</details>

<details><summary>Hint 2 — policy shape</summary>

Use `aws_iam_policy_document` to generate a deny statement conditioned on `aws:SecureTransport` being false. The deny applies to any principal and both the bucket ARN and its `/*` objects. Install it with `aws_s3_bucket_policy`.
</details>

<details><summary>Hint 3 — state versus object data</summary>

The sample object is uploaded with AWS CLI, so Terraform does not track it as a managed resource. Bucket `force_destroy` deletes even these untracked versions during lab teardown. That is why the bucket must be dedicated to this game.
</details>
