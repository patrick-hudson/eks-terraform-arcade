# Answer · six controls, one disposable bucket

`solution/main.tf` is the complete implementation. Its bucket uses a provider-generated unique suffix; the remaining resources configure ownership, public access, versioning, encryption and a TLS-only bucket policy. It uses SSE-S3 rather than a customer KMS key to avoid key charges and an unrelated policy exercise.

To use the reference code, keep the same state directory:

```bash
: "${LAB_ROOT:?Set LAB_ROOT to the extracted package directory}"
cd "$LAB_ROOT/run/01-private-s3"
cp "$LAB_ROOT/labs/01-private-s3/solution/main.tf" main.tf
terraform init
terraform fmt
terraform validate
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
export BUCKET="$(terraform output -raw bucket_name)"
```

Return to the mission's upload, verification and destroy commands. A plan includes six managed resources: the bucket and five configuration resources. The policy document is a local data source, not another cloud resource.

Encryption protects stored bytes, IAM and resource policies decide who can use them, and TLS protects bytes in transit. An explicit deny wins over an applicable allow. Public access blocking is still worthwhile even when the only current policy is private: it prevents later accidental public ACLs and policies.

Deleting a current version usually creates a delete marker; older versions remain available and billable. Destroy needs to remove versions and markers as well as the current object. The lab-only `force_destroy` does this. A production answer would discuss retention, recovery and a separate deliberate deletion process rather than copying this setting everywhere.

The TLS statement targets the bucket ARN for bucket-level actions and `bucket-arn/*` for object-level actions. It grants no access by itself. The CLI succeeds because your lab operator identity has permission; the unsigned HTTPS request returns 403.
