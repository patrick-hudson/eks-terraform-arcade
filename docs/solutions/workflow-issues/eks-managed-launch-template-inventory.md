---
title: Inventory the EKS-managed launch template before teardown
date: "2026-10-05"
category: workflow-issues
module: EKS cloud proof
problem_type: workflow_issue
component: infrastructure
severity: medium
applies_when:
  - "Recording resources created by a disposable EKS managed node group"
  - "Verifying cleanup beyond the objects listed in Terraform state"
tags: [eks, cleanup, autoscaling, launch-template, ownership]
---

# Inventory the EKS-managed launch template before teardown

## Context

During the October 5, 2026 EKS 1.37 test, the node group referenced the launch template authored by Terraform. Its Auto Scaling group had a null top-level `LaunchTemplate`, but a second template appeared under `MixedInstancesPolicy.LaunchTemplate.LaunchTemplateSpecification`. The second template's creation time was inside the test window, and its creator was the EKS node-group service role.

Reading only Terraform state, the node-group template or the Auto Scaling group's top-level template would have missed that service-created child. The test captured it in a supplemental resource ledger before teardown. This was an inventory gap; no orphan or AWS deletion defect was established by that observation.

## Guidance

Capture service-created children while their parents still exist. Start from the exact node group created by the test, follow its reported Auto Scaling group names, and inspect both template locations. The AWS API documents the nested [mixed-instances policy](https://docs.aws.amazon.com/autoscaling/ec2/APIReference/API_MixedInstancesPolicy.html) and its [launch-template specification](https://docs.aws.amazon.com/autoscaling/ec2/APIReference/API_LaunchTemplate.html).

The following are read-only observations. Set `AWS_PROFILE`, `AWS_REGION`, `CLUSTER_NAME` and `NODEGROUP_NAME` to the reviewed test environment. Set `ASG_NAME` to a name returned by the first command; repeat the second command for each returned group.

```bash
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" eks describe-nodegroup \
  --cluster-name "$CLUSTER_NAME" --nodegroup-name "$NODEGROUP_NAME" \
  --query 'nodegroup.resources.autoScalingGroups[].name' --output json

aws --profile "$AWS_PROFILE" --region "$AWS_REGION" autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names "$ASG_NAME" \
  --query 'AutoScalingGroups[].{arn:AutoScalingGroupARN,direct:LaunchTemplate,mixed:MixedInstancesPolicy.LaunchTemplate}' \
  --output json
```

Record each exact template ID, its parent group ARN, creation time and creator. If a report constructs an ARN from a returned ID, label it as derived rather than claiming AWS returned it. Establish ownership from the parent relationship and the test's baseline; a familiar name prefix alone is insufficient.

Destroy through the reviewed Terraform workflow first. Then check the exact recorded child IDs through AWS. Empty Terraform state is not proof that service-created children disappeared. A permission error is also not absence. Preserve any unresolved child in the cleanup report and retain the recovery evidence.

## Why this matters

The parent relationship is easiest to establish before deleting the node group. Discovering a leftover template afterward can require reconstructing ownership from timestamps and audit history. The template in this test was captured separately without racing the running harness's ledger writer, then assigned its own final absence check.

## When to apply

Use this when auditing a managed node group's resource inventory. The observed response shape is not a promise that every EKS node group uses the same Auto Scaling settings. Inspect the actual response, including any per-instance overrides, rather than assuming a single template field covers every configuration. This lesson does not authorize deleting unrelated launch templates or service-linked roles.

## Related

- [Cost and cleanup](../../cost-and-cleanup.md)
- [Validation record](../../VALIDATION.md)
