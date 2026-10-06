# Keep the practice below your $20 allowance

For a detailed teardown audit, also capture service-created children before deleting their parents. The [EKS launch-template inventory lesson](solutions/workflow-issues/eks-managed-launch-template-inventory.md) explains one child that Terraform state alone can miss.

**Target expected spend: under $5. Personal allowance: $20 total.** Eight total billable EKS hours, one worker normally and two briefly, small datasets, and prompt deletion leave a substantial buffer. This is an estimate, not an AWS spending cap. Count provisioning, troubleshooting and deletion time too. Rates below use **US West (Oregon), `us-west-2`**, checked against AWS’s public regional price lists on October 4, 2026, before tax and without free-tier credits.

| Component | Planning rate | Kit default |
|---|---:|---|
| EKS standard-support control plane | $0.10/hour | One shared cluster per session |
| EKS extended support | $0.60/hour | Avoided by supported version and STANDARD policy |
| t3.medium Linux, shared On-Demand | $0.0416/hour | One node, maximum two |
| Public IPv4 | $0.005/address-hour | One per worker |
| gp3 | $0.08/GiB-month | 20GiB root per worker; 1GiB storage exercise |
| NAT gateway | $0.045/hour plus processing and IPv4 | None |
| Application load balancer | $0.0225/hour plus LCU and IPv4 | None |
| S3 / DynamoDB / Lambda / logs | Usage based | Tiny objects and <=10 function calls |

Regional rate sources: [EC2, EBS and NAT — Oregon CSV](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-west-2/index.csv), [EKS — Oregon](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEKS/current/us-west-2/index.json), [public IPv4 — Oregon](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/us-west-2/index.json), [ALB — Oregon](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/us-west-2/index.json). These are public download URLs; their `us-east-1` hostname is AWS’s price-list service, while `/us-west-2/` selects the workload region. The EC2 rows are `USW2-BoxUsage:t3.medium`, `USW2-EBS:VolumeUsage.gp3` and `USW2-NatGateway-Hours`. Billing rules: [EKS](https://aws.amazon.com/eks/pricing/), [EC2](https://aws.amazon.com/ec2/pricing/on-demand/), [EBS](https://aws.amazon.com/ebs/pricing/), [VPC](https://aws.amazon.com/vpc/pricing/).

```text
One-worker hourly base:
0.10 + 0.0416 + 0.005 + (20 × 0.08 / 730) = about $0.149/hour
2 hours ≈ $0.30; 8 hours ≈ $1.19

Two-worker hourly base:
0.10 + 2 × (0.0416 + 0.005 + 20 × 0.08 / 730) = about $0.198/hour
2 hours ≈ $0.40; 8 hours ≈ $1.59
```

Reserve another ~$3 for small-service labs, transfer, logging, temporary replacement capacity and retries. The [first live smoke test](aws-testing.md) uses part of that same reserve; do not add its $3 reserve again. Its bounded Lambda/DynamoDB workload should cost well under $1. Optional EKS validation also counts toward the eight total EKS hours. Leave the rest of the $20 untouched. Request counts, egress, duration, price changes and resources outside these examples can raise the bill. Extra nodes during updates can temporarily exceed desired count. T3 standard credits avoid surplus-credit charges but may throttle under sustained CPU work; do not switch to Unlimited just to run a stress test.

**An idle cluster still bills.** A forgotten 730-hour month is roughly $109 with one worker or $144 with two. Deleting nodes leaves the control plane billing. Stopping EC2 leaves EBS billing. A reminder or tag never deletes infrastructure by itself.

## Budget notifications (optional setup, recommended)

Create a **monthly account-wide cost budget** of $20 with actual-spend alerts at $5, $10 and $15. Account-wide includes unrelated usage. In a shared account, keep the lab session ledger separately so pre-existing charges do not look like practice spend; do not alter other teams’ budgets or resources. Notifications can arrive late: AWS updates budget data up to three times daily, typically 8–12 hours apart. They do not automatically shut down resources or enforce your $20 allowance. [AWS Budgets update frequency](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

These commands create one budget and email subscriptions when **you** run them. Supply an email you control. Billing/Budgets permissions may differ from infrastructure permissions.

```bash
cd "$LAB_ROOT/run"
read -r -p 'Email address for your cost alerts: ' BUDGET_EMAIL
export LAB_BUDGET_NAME="${TF_VAR_lab_id}-interview-$(date +%Y-%m)"
jq -n --arg name "$LAB_BUDGET_NAME" \
  '{BudgetName:$name,BudgetLimit:{Amount:"20",Unit:"USD"},TimeUnit:"MONTHLY",BudgetType:"COST"}' > budget.json
jq -n --arg email "$BUDGET_EMAIL" \
  '[5,10,15] | map({Notification:{NotificationType:"ACTUAL",ComparisonOperator:"GREATER_THAN",Threshold:.,ThresholdType:"ABSOLUTE_VALUE"},Subscribers:[{SubscriptionType:"EMAIL",Address:$email}]})' > notifications.json
aws budgets create-budget --account-id "$TF_VAR_expected_account_id" \
  --budget file://budget.json --notifications-with-subscribers file://notifications.json
aws budgets describe-budget --account-id "$TF_VAR_expected_account_id" --budget-name "$LAB_BUDGET_NAME"
```

If the name already exists, inspect the existing budget instead of creating duplicates. A calendar-month budget resets monthly; **your $20 total practice allowance does not**. Keep a session ledger across months. Remove the budget only if no longer useful:

```bash
aws budgets delete-budget --account-id "$TF_VAR_expected_account_id" --budget-name "$LAB_BUDGET_NAME"
```

## Estimates and inventory in the session controls

The browser’s **Environment** tab and the TUI show the same dated **1-hour and 2-hour estimates** as `./arcade session status ID`. Open the assumptions to distinguish the selected mission’s extra cost from its shared Game 07 foundation. The default foundation estimate is **$0.1488/hour**, approximately **$0.15 for one hour** or **$0.30 for two hours**. Count that shared foundation once across simultaneous exercises, not once for every mission. A displayed $0 base for a usage-based service does not mean its requests, storage, logs or transfer are free.

The estimates are authored planning assumptions, not live billing data or a hard spending cap. They do not start or stop with the practice timer. Provisioning, failed attempts and deletion all take billable time; only verified resource cleanup establishes the end of that exposure.

Use **Plan cleanup** in the browser or **Plan destroy** in the TUI, review the separate saved plan and type its `DESTROY` approval. CLI equivalents are `./arcade session plan_destroy ID` followed by `./arcade session apply ID`; include the same `--root` for multi-root missions. Deletion follows reverse dependency order. Games 09/10 remove `workload` before infrastructure (`.`); Game 13 removes `access` before `workload`; all precede Game 07.

The session retains observed Terraform addresses, types, IDs and ARNs and the last operation result across failures and destruction. It does not expose full state, credentials or arbitrary resource attributes. Use **Resource inventory** in the browser, **i** from a TUI mission, or the CLI status JSON to recover those identifiers. Keep additional IDs for resources created by controllers or outside Terraform, such as a backing EBS volume.

A repair receipt after destruction may include bounded cleanup observations. The retained inventory’s **Cloud absence: unknown** field still means it does not certify absence. Empty state, an absent workspace or a failed API call cannot establish deletion. Preserve state and inputs after a failed cleanup and perform the named-resource checks below and in the mission runbook.

## Session ledger

| Session | Start UTC | Cluster deleted UTC | Worker count | Hours | Estimated spend | Next-day actual |
|---|---|---|---:|---:|---:|---:|
| Terraform/AWS | | | 0 | | | |
| EKS session 1 | | | 1–2 | | | |
| EKS session 2 | | | 1–2 | | | |

Set a phone timer for the session and reserve 20–30 minutes for cleanup. This kit does not install a scheduled cleanup process; an external timer is a reminder, and you still verify deletion.

## Teardown order: apps → storage → identities/add-ons → EKS → network

1. While the cluster is alive, capture cluster name, VPC ID and each dynamically created EBS volume ID. Save them in `run/session-resources.txt`.
2. Destroy each attempted gauntlet workload Terraform root and the Game 08/09 workload roots. Game 09 uses `run/09-pod-identity/workload`; Game 10 uses `run/10-ebs-storage/workload`. For Game 10, destroy that workload state while CSI is alive and wait for its captured backing EBS volume to disappear **before** destroying the CSI driver. Its cleanup script has the exact commands and the unbound-PVC path.
3. If you attempted Game 13, destroy its `access` state first, verify the exact ingress rule is absent and the public path is closed, then destroy its `workload` state. It reuses the arena’s node IPv4 and adds no load balancer. If you authored an Ingress or `LoadBalancer` stretch, remove it through its owning Terraform state while the controller still runs and confirm its AWS load balancer is gone.
4. Destroy the Game 10 AWS root, then the Game 09 AWS root, then the Game 07 foundation state. The capstone reuses Game 08 state; it has no second owner of `arcade-app`. Preserve state and retry a failed destroy after resolving the dependency; do not clear Kubernetes finalizers to conceal a stuck cloud resource.
5. Destroy all standalone labs, including lab02 workload and backend bootstrap in their documented order. Backend comes last, after state migration back to local.
6. Run the read-only audit below and inspect AWS billing the following day. Service deletion evidence is immediate; billing evidence is delayed.

Use the same working directories, profile, account and region that created the resources. Every planned destroy should name only the known lab-owned resources. In a shared account, read-only inventory may show unrelated resources; never treat that list as an instruction to delete them. Do not replace Terraform destroy with manual console deletions, namespace deletions, or removing entries from state.

[Official EKS deletion order](https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html) explains why controllers must clean up their resources before the cluster is removed.

## Audit: evidence beyond an empty state

Before destroying lab07:

```bash
export LAB_CLUSTER_NAME=$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)
export LAB_VPC_ID=$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw vpc_id)
printf 'cluster=%s\nvpc=%s\n' "$LAB_CLUSTER_NAME" "$LAB_VPC_ID" > "$LAB_ROOT/run/session-resources.txt"
```

After deletion:

```bash
bash "$LAB_ROOT/scripts/audit-aws.sh"
```

The audit is read-only. It exits nonzero if the captured cluster still exists or an API check fails; other inventories still require manual inspection, so exit 0 does not certify that the account has no billable leftovers. A listing is not a command to delete everything returned. Tagging APIs do not find every untagged/controller-created object, so wider EBS, address and snapshot inventories are intentional. Identify your resources by captured IDs, tags and creation time. A failed listing due to AccessDenied is **not** proof of no leftovers. Also verify lab-specific S3 buckets (including object versions), IAM roles/policies, Lambda/table/log-group names and backend buckets using their runbooks. [Tagging API coverage](https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html)

Paid leftovers to watch: EKS clusters, EC2 workers, EBS volumes/snapshots, load balancers, NAT gateways, Elastic IPs, interface endpoints, log groups, versioned S3 data, ECR images, optional KMS keys or backups. The supplied labs avoid most of these; your experiments may add them.
