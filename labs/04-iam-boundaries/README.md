# 04 — Permission to read, permission to fail

**45 minutes · IAM + Terraform · $0 direct IAM charge · broken start.** No S3 bucket is provisioned here. You are testing identity-policy and permissions-boundary evaluation against example object ARNs. A successful simulator result is not proof of a successful S3 request.

## Your assignment

An application role should read objects under `published/`, but never read `private/`, list the bucket, or write objects. The shipped policy does not pass acceptance. Keep the boundary; do not replace policies with `*` or AdministratorAccess. Explain role trust versus role permissions and the intersection with a permissions boundary.

Write `aws_iam_policy`, `aws_iam_role`, and `aws_iam_role_policy`; use `jsonencode`. For build mode start with `starter/TASKS.md`; for incident mode follow this runbook. The full implementation is in `solution/`, but start it with the fault flag below.

## Start the incident

Complete [setup](../../docs/setup.md), then:

```bash
mkdir -p "$LAB_ROOT/run/04-iam-boundaries"
cp "$LAB_ROOT/labs/04-iam-boundaries/solution/"*.tf "$LAB_ROOT/run/04-iam-boundaries/"
cp "$LAB_ROOT/labs/04-iam-boundaries/solution/.terraform.lock.hcl" "$LAB_ROOT/run/04-iam-boundaries/"
cd "$LAB_ROOT/run/04-iam-boundaries"
terraform init
terraform fmt -check
terraform validate
terraform plan -var='policy_variant=broken' -out=apply.tfplan
terraform show apply.tfplan
terraform apply apply.tfplan
ROLE_ARN=$(terraform output -raw role_arn)
BUCKET_ARN=$(terraform output -raw bucket_arn)
aws iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names s3:GetObject --resource-arns "$BUCKET_ARN/published/hello.txt" \
  --query 'EvaluationResults[].{Decision:EvalDecision,Boundary:PermissionsBoundaryDecisionDetail}'
```

Allow several seconds for IAM propagation, then repeat the read-only simulation if needed. Desired outcome is `allowed`; the first run will not meet it. `AccessDenied` on the simulator API itself means your operator lacks `iam:SimulatePrincipalPolicy`; that is setup, not the injected fault.

Inspect the role, inline policy and boundary using Terraform state and these commands:

```bash
aws iam get-role --role-name "$(terraform output -raw role_name)"
aws iam get-role-policy --role-name "$(terraform output -raw role_name)" --policy-name read-one-prefix
aws iam get-policy --policy-arn "$(terraform output -raw boundary_arn)"
terraform state show aws_iam_role_policy.read
```

Record a hypothesis before opening [hints](HINTS.md). The repair is in [ANSWERS.md](ANSWERS.md).

## Acceptance

Run each action/resource pair separately so the result is unambiguous:

```bash
aws iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names s3:GetObject --resource-arns "$BUCKET_ARN/published/hello.txt" \
  --query 'EvaluationResults[0].EvalDecision' --output text
aws iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names s3:GetObject --resource-arns "$BUCKET_ARN/private/secret.txt" \
  --query 'EvaluationResults[0].EvalDecision' --output text
aws iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names s3:PutObject --resource-arns "$BUCKET_ARN/published/hello.txt" \
  --query 'EvaluationResults[0].EvalDecision' --output text
aws iam simulate-principal-policy --policy-source-arn "$ROLE_ARN" \
  --action-names s3:ListBucket --resource-arns "$BUCKET_ARN" \
  --query 'EvaluationResults[0].EvalDecision' --output text
```

Expected sequence after repair: allowed, implicitDeny, implicitDeny, implicitDeny. Show an empty Terraform plan after applying the repair. Explain why adding an identity allow for `private/` still cannot grant access through this boundary. Discuss SCPs, resource policies, session policies and explicit denies; this simulation does not reproduce every live-policy interaction.

## Teardown, fixed or broken

```bash
ROLE_NAME=$(terraform output -raw role_name)
BOUNDARY_ARN=$(terraform output -raw boundary_arn)
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
aws iam get-role --role-name "$ROLE_NAME"
aws iam get-policy --policy-arn "$BOUNDARY_ARN"
```

State should be empty; the last two commands should report `NoSuchEntity`. Do not treat an authorization/network failure as successful deletion.

Sources: [policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html), [permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html), [simulator limitations](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html).
