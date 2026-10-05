# 01 · Private artifact vault

**35–50 minutes · mid-senior · budget $0.05 for tiny objects and a short session.** Build a disposable, private, versioned S3 bucket. There is no compute, KMS key or data transfer workload. The estimate is an allowance, not a billing cap; object bytes, versions and API requests cost money. Keep the two sample objects small and destroy today. [S3 pricing](https://aws.amazon.com/s3/pricing/).

Your review brief: create a uniquely named bucket with `bucket_prefix`; block all public access; enforce bucket ownership without ACLs; enable versioning and explicit SSE-S3 (`AES256`); deny non-TLS requests; export `bucket_name` and `bucket_arn`. Use the supplied account guard and tags. Demonstrate two versions, retrieve the current object, and prove unsigned access fails. Explain encryption, authorization and transport security as separate controls.

Use `force_destroy = true` **only because this is a disposable lab bucket**. It allows Terraform to delete every object version during teardown. Never put personal files, production artifacts or real state in this bucket. Production retention and deletion protection are different requirements.

From the extracted package directory, initialize your working copy. Complete [setup](../../docs/setup.md) first; `TF_VAR_expected_account_id` must be the intended lab account, not a production account.

```bash
export LAB_ROOT="$(pwd)"
test -d "$LAB_ROOT/labs/01-private-s3"
: "${TF_VAR_expected_account_id:?Set the intended dedicated lab account ID first}"
export AWS_REGION="${TF_VAR_region:-us-west-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export TF_VAR_region="$AWS_REGION"
test "$(aws sts get-caller-identity --query Account --output text)" = "$TF_VAR_expected_account_id"
mkdir -p "$LAB_ROOT/run/01-private-s3"
cp "$LAB_ROOT/labs/01-private-s3/starter/"*.tf "$LAB_ROOT/run/01-private-s3/"
cp "$LAB_ROOT/labs/01-private-s3/solution/.terraform.lock.hcl" "$LAB_ROOT/run/01-private-s3/"
cd "$LAB_ROOT/run/01-private-s3"
${EDITOR:-vi} main.tf
terraform init
terraform fmt
terraform validate
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
export BUCKET="$(terraform output -raw bucket_name)"
```

The starter provides provider configuration and resource requirements. Write the resources before planning. [HINTS.md](HINTS.md) offers layered help; [ANSWERS.md](ANSWERS.md) gives code orientation and the exact reference-solution command.

Create evidence and verify the controls:

```bash
printf 'release-one\n' > evidence.txt
aws s3api put-object --bucket "$BUCKET" --key evidence.txt --body evidence.txt
printf 'release-two\n' > evidence.txt
aws s3api put-object --bucket "$BUCKET" --key evidence.txt --body evidence.txt
aws s3api get-object --bucket "$BUCKET" --key evidence.txt downloaded.txt
cmp evidence.txt downloaded.txt
aws s3api get-public-access-block --bucket "$BUCKET" |
  jq -e '.PublicAccessBlockConfiguration | [.[]] | all(. == true)'
aws s3api get-bucket-versioning --bucket "$BUCKET" |
  jq -e '.Status == "Enabled"'
aws s3api get-bucket-encryption --bucket "$BUCKET" |
  jq -e '.ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm == "AES256"'
aws s3api list-object-versions --bucket "$BUCKET" --prefix evidence.txt |
  jq -e '[.Versions[] | select(.Key == "evidence.txt")] | length >= 2'
HTTP_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "https://${BUCKET}.s3.${AWS_REGION}.amazonaws.com/evidence.txt")"
test "$HTTP_STATUS" = 403
terraform plan -detailed-exitcode
# Required: final plan returns 0. Every jq/test/cmp check above succeeds.
```

If a newly enabled versioned bucket briefly returns `NoSuchKey`, allow versioning to propagate and retry the sample operations; AWS recommends allowing up to 15 minutes after first enabling it. This lab has no hourly bucket fee. [Versioning behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/manage-versioning-examples.html).

Interview follow-ups: why does default encryption not grant access? Why is an explicit deny stronger than an allow? What disappears after a versioned object delete, and what remains billable? Why does a bucket policy need both bucket and object ARNs for this deny?

Destroy even if the mission is unfinished:

```bash
cd "$LAB_ROOT/run/01-private-s3"
export BUCKET="$(terraform output -raw bucket_name)"
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
aws s3api wait bucket-not-exists --bucket "$BUCKET"
terraform show -json | jq -e '[.values.root_module.resources[]? | select(.mode == "managed")] | length == 0'
```

A successful waiter plus no managed resources is the completion condition. If apply failed before outputs were saved, obtain the bucket name from `terraform state show aws_s3_bucket.lab`, then destroy using the same directory. If the Terraform configuration is invalid, save your attempted code and restore `solution/main.tf` before destroying. Preserve state until cleanup succeeds.

References: [S3 public access controls](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html), [SSE-S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html), [Terraform S3 bucket resource](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket).
