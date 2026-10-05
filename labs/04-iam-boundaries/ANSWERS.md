# Answer — 04

The broken identity policy grants `s3:GetObject` on the bucket ARN. That action needs an **object ARN**. A bucket ARN does not cover its contents.

```bash
cd "$LAB_ROOT/run/04-iam-boundaries"
terraform plan -var='policy_variant=fixed' -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
terraform plan -var='policy_variant=fixed'
```

The fixed identity policy permits object reads at `bucket/*`; the boundary limits those reads to `bucket/published/*`. The boundary does not grant access by itself. Keeping both as separate policies lets you show the intersection. Least privilege could narrow both to `published/*`; the broader identity allow is deliberate here to expose boundary behavior.

The role trusts the Lambda service; it is not an interactive user role. `simulate-principal-policy` evaluates its permissions without assuming it. A production data-plane proof would need a real bucket, object, role session, and evaluation of resource policies and organization controls.

Senior follow-ups: how could a resource policy naming a session principal change boundary behavior? Why doesn't `sensitive = true` encrypt state? Who should have `iam:PutRolePermissionsBoundary` or `iam:DeleteRolePermissionsBoundary`?
