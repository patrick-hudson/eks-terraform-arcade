# Real AWS testing, with a small bill and a deletion receipt

**Status: prepared locally; no AWS test has run.** The first cloud test is **Game 05 only**: one Python 3.14 Lambda, one on-demand DynamoDB table, one log group, one execution role and its inline policy. It tests a deliberately wrong environment variable, repairs it, proves two atomic increments, checks invalid input, then destroys everything. This gives useful coverage of Terraform, deployment ordering, IAM, packaging and live AWS behavior in one small stack. EKS is a separate follow-up, not part of this first run.

We expect **well under $1** for this test. Reserve **$3 of the overall $20 allowance** for cloud validation and keep the rest for practice. These are operating allowances, not enforced AWS spending limits.

## What you need to provide

Use a dedicated sandbox account with no production data. Have a non-root identity available in that account, with MFA and a short-lived local login. You sign in on this computer; **do not send access keys, session tokens, passwords or login authorization codes in chat**.

After setup, share only:

- The local profile name, normally `arcade-smoke`.
- The intended 12-digit sandbox account ID and region, normally `us-west-2`.
- Whether this is a dedicated sandbox, and any organization restrictions or mandatory IAM permissions boundary.
- Approval for the concrete Game 05 create → break → repair → verify → destroy run after its plan is reviewed.

The account ID and IAM role ARN identify the destination; they are not authentication secrets. Creating a local profile alone is not approval to create resources. The browser application never receives or handles AWS credentials.

## Sign in locally

### For your existing account without SSO

You do not need to set up SSO for this test. AWS CLI 2.32.0+ supports browser login. Use your existing non-root IAM or federated identity. Its administrator grants the AWS managed policy [`SignInLocalDevelopmentAccess`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/SignInLocalDevelopmentAccess.html), ARN `arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess`, as well as the lab permissions below. Sign-in permission does not grant infrastructure access. The kit's pinned CLI is newer than that minimum. [AWS browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
aws login --profile arcade-browser --region us-west-2
aws configure set region us-west-2 --profile arcade-smoke
aws configure set credential_process \
  'aws configure export-credentials --profile arcade-browser --format process' \
  --profile arcade-smoke
aws sts get-caller-identity --profile arcade-smoke --region us-west-2 \
  --query '{Account:Account,Arn:Arn}' --output json
```

This separate process profile lets Terraform consume the temporary credentials through the CLI even if its SDK does not understand `login_session`. The command is stored as configuration; **do not run `export-credentials` directly or paste its output**. Renew the browser session with `aws login --profile arcade-browser` when needed. A headless terminal can use `aws login --remote --profile arcade-browser --region us-west-2`; enter the returned authorization code only into that terminal. [AWS process-profile compatibility example](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)

Use your existing IAM user or role, with MFA. Use fresh profile names if either name already points at an unrelated account; do not overwrite a production profile. Prepare the local run below, then have its administrator attach the named-resource operator policy to that identity. Sign in to the browser as that identity before running `aws login`; no new access key is needed. [MFA assignment](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable_virtual.html).

### If you already use IAM Identity Center / AWS SSO

Run these yourself in a terminal. Enter your access portal URL, SSO region, sandbox account and assigned permission set when prompted. The SSO region can differ from the workload region. [AWS CLI SSO configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)

```bash
aws --version
aws configure sso --profile arcade-smoke
aws sso login --profile arcade-smoke
aws configure set region us-west-2 --profile arcade-smoke
aws sts get-caller-identity --profile arcade-smoke --region us-west-2 \
  --query '{Account:Account,Arn:Arn}' --output json
```

If the browser is on a different device, use the supported device-code flow:

```bash
aws configure sso --profile arcade-smoke --use-device-code
aws sso login --profile arcade-smoke --use-device-code
```

## Prepare the exact scope before granting access

Activate the project environment once in your terminal. These commands then work from any directory. Replace the example account ID with your sandbox account:

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
python3 "$LAB_ROOT/scripts/smoke-aws.py" prepare \
  --profile arcade-smoke \
  --account-id 123456789012 \
  --region us-west-2
```

`prepare` is local only. It creates a fresh `run/smoke-<8hex>` directory and prints the actual path. Keep that directory; it will contain the state needed for recovery. Its basename is the lab ID, such as `smoke-a1b2c3d4`. **Use the ID actually printed**, not this example, in the policy below. The generated, SHA-256-tracked `smoke_override.tf` gives the inline policy a deterministic name; keep it with the copied lab files. The five Terraform-managed resources are:

| Resource | Exact name for the prepared run |
|---|---|
| Lambda and DynamoDB table | `SMOKE_ID-05-counter` |
| CloudWatch log group | `/aws/lambda/SMOKE_ID-05-counter` |
| Lambda execution role | `SMOKE_ID-05-lambda` |
| Role inline policy | `SMOKE_ID-05-policy` |

### Permissions for your operator identity

An account administrator can attach the following policy to the sandbox role or permission set you use. Replace **all** `ACCOUNT_ID`, `REGION`, and `SMOKE_ID` placeholders first; use `us-west-2` for `REGION`. This is a source-reviewed policy for the five resources in the current Game 05; **its completeness still needs the first live run**. An organization SCP or permissions boundary can still deny these actions.

The three Terraform refresh details people commonly miss are Lambda code-signing/version reads, DynamoDB backup/TTL reads, and IAM inline/attached-policy reads. They are needed even though the test creates no code-signing configuration, backups, TTL or managed policy attachments. The current provider code documents those reads: [Lambda](https://github.com/hashicorp/terraform-provider-aws/blob/v6.67.0/internal/service/lambda/function.go), [DynamoDB](https://github.com/hashicorp/terraform-provider-aws/blob/v6.67.0/internal/service/dynamodb/table.go), [IAM role](https://github.com/hashicorp/terraform-provider-aws/blob/v6.67.0/internal/service/iam/role.go).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SmokeFunction",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction", "lambda:DeleteFunction",
        "lambda:GetFunction", "lambda:GetFunctionConfiguration",
        "lambda:GetFunctionCodeSigningConfig", "lambda:ListVersionsByFunction",
        "lambda:UpdateFunctionConfiguration", "lambda:UpdateFunctionCode",
        "lambda:ListTags", "lambda:TagResource", "lambda:UntagResource",
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:SMOKE_ID-05-counter"
    },
    {
      "Sid": "SmokeTable",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable", "dynamodb:DeleteTable",
        "dynamodb:DescribeTable", "dynamodb:DescribeContinuousBackups",
        "dynamodb:DescribeTimeToLive", "dynamodb:ListTagsOfResource",
        "dynamodb:TagResource", "dynamodb:UntagResource", "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/SMOKE_ID-05-counter"
    },
    {
      "Sid": "SmokeLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup", "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy",
        "logs:ListTagsForResource", "logs:TagResource", "logs:UntagResource",
        "logs:ListTagsLogGroup", "logs:TagLogGroup", "logs:UntagLogGroup",
        "logs:DescribeLogStreams", "logs:FilterLogEvents", "logs:GetLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:REGION:ACCOUNT_ID:log-group:/aws/lambda/SMOKE_ID-05-counter",
        "arn:aws:logs:REGION:ACCOUNT_ID:log-group:/aws/lambda/SMOKE_ID-05-counter:*"
      ]
    },
    {
      "Sid": "ListLogGroupMetadataForCleanup",
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "*",
      "Condition": {"StringEquals": {"aws:RequestedRegion": "REGION"}}
    },
    {
      "Sid": "SmokeExecutionRole",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
        "iam:TagRole", "iam:UntagRole", "iam:ListRoleTags",
        "iam:ListRolePolicies", "iam:GetRolePolicy",
        "iam:PutRolePolicy", "iam:DeleteRolePolicy",
        "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole"
      ],
      "Resource": "arn:aws:iam::ACCOUNT_ID:role/SMOKE_ID-05-lambda"
    },
    {
      "Sid": "PassOnlyTheSmokeRoleToLambda",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::ACCOUNT_ID:role/SMOKE_ID-05-lambda",
      "Condition": {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}}
    }
  ]
}
```

`sts:GetCallerIdentity` requires no explicit allow. `logs:DescribeLogGroups` needs `Resource: "*"`, so it can reveal other log-group metadata in the selected region. The function execution policy is narrower than the operator policy: only `dynamodb:UpdateItem` on its table and log-stream writes in its log group. [Identity lookup](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html), [PassRole scoping](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html).

**Role creation plus inline-policy editing is privileged.** Resource-name restrictions do not make arbitrary Terraform harmless: a modified trust or permission policy could grant the new role wider access. Use this policy in the dedicated sandbox and review the saved plan. If you must use a shared account, have its owner supply an approved permissions boundary and adjust the Terraform before proceeding; the unmodified lab does not attach a boundary. Do not solve a denial by attaching `AdministratorAccess`.

## The first run and its evidence

With your login ready and the concrete run approved, the plan-only command performs an identity check, initializes providers, validates the configuration and produces a saved Terraform plan. It makes AWS read calls but does not create infrastructure:

```bash
python3 "$LAB_ROOT/scripts/smoke-aws.py" run --run-dir "$LAB_ROOT/run/smoke-a1b2c3d4"
```

Review the displayed account, region, names, five managed resources and plan. Expect the deliberately wrong `COUNTER_TABLE` key, 128 MiB memory, a five-second timeout, on-demand DynamoDB and one-day log retention. There should be no networking resources, public invocation URL, API Gateway, schedules or extra services. The CLI prints a plan SHA-256.

After approval, supply that exact digest. Do not copy this placeholder literally:

```bash
python3 "$LAB_ROOT/scripts/smoke-aws.py" run \
  --run-dir "$LAB_ROOT/run/smoke-a1b2c3d4" \
  --execute --approve-plan PLAN_SHA256_PRINTED_BY_THE_PREVIOUS_COMMAND
```

The test must produce evidence for each claim:

1. The saved plan creates exactly the intended stack in the intended account.
2. Invocation of the broken deployment returns a Lambda `FunctionError`; a successful Invoke HTTP response alone is insufficient.
3. Terraform changes the environment key to `TABLE_NAME`, without replacing the function or broadening IAM permissions.
4. Two valid invocations return consecutive visit counts; a strongly consistent DynamoDB read matches the result.
5. Invalid input returns the handler's 400 response and does not increment the stored item.
6. A fresh Terraform plan has no changes.
7. Teardown empties Terraform's managed state, and named AWS queries prove the function, table, log group and execution role are gone.

The driver limits invocation count and attempts cleanup on failures. It cannot guarantee cleanup after power loss, process termination or expired credentials. After an interruption, renew the login and use the same directory:

```bash
python3 "$LAB_ROOT/scripts/smoke-aws.py" cleanup \
  --run-dir "$LAB_ROOT/run/smoke-a1b2c3d4" --execute
```

A `ResourceNotFoundException` / IAM `NoSuchEntity` proves a named resource is absent; `AccessDenied`, timeouts and expired tokens do not. Preserve state and logs until cleanup is verified. If a provider created a resource but failed before recording it in state, retain the exact resource name and reconcile that orphan explicitly rather than declaring empty state sufficient. Signing out, closing the app and reaching a timer do not delete AWS resources.

## Cost basis and optional EKS pass

Rates checked October 4, 2026 against AWS’s public **US West (Oregon), `us-west-2`** price lists, before tax and without assuming credits. Ten 128 MiB Lambda calls lasting five seconds each total 6.25 GB-seconds: about **$0.000104 compute plus $0.000002 requests** at $0.0000166667 per GB-second and $0.20 per million requests. Initialization, logging and tiny table storage add usage; the expected total remains far below $1 for this bounded workload. DynamoDB Standard on-demand Oregon rates are $0.625 per million write request units and $0.125 per million read request units. This test uses only a handful. [Lambda Oregon rate list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/us-west-2/index.json), [DynamoDB Oregon rate list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/us-west-2/index.json).

After that succeeds, an optional separate EKS test can cover the things Lambda cannot: **one EKS 1.36 cluster, one `t3.medium` node, healthy add-ons, one ImagePullBackOff repair and one missing-configuration repair**. Aim for 90 minutes including creation and deletion, reserve **up to $2**, and do not run the EBS, Pod Identity or every incident in that first pass. It needs separate EKS/EC2/IAM permissions, the permanent administrator role ARN and your current public IPv4 `/32`; the Game 05 policy intentionally cannot create a cluster.

At the kit's roughly $0.149/hour one-node Oregon rate, 90 minutes is about $0.23 before retries and small transfer charges ($0.30 if two nodes run for the full period). The $2 allowance provides room for delays; it is not a promise or service limit. The $0.10/hour standard-support control plane, worker, public IPv4 and disk all count while provisioning and deleting. Use one node, standard T3 credits, 20 GiB gp3, no NAT gateway and no load balancer. [EKS pricing](https://aws.amazon.com/eks/pricing/), [Oregon EC2/EBS rates](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-west-2/index.csv), [EBS](https://aws.amazon.com/ebs/pricing/), [public IPv4](https://aws.amazon.com/vpc/pricing/), [kit cost calculation](cost-and-cleanup.md).

Use the account-wide $20 budget alerts described in the [cost guide](cost-and-cleanup.md), but keep a record of test duration and cleanup independently. AWS Budgets updates can lag; alerts do **not** impose a hard spending cap. A credential session expiring also does not stop billing. [AWS Budgets behavior](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

## What this validates, and what remains pending

Local checks can validate the runner's allowlist, failure paths and assertions using fixtures. They cannot establish AWS account permissions, regional runtime availability, service propagation behavior or successful deletion. Only a completed cloud receipt should change those claims to “live verified.” The first Game 05 result would not validate EKS, S3, EBS or the rest of the curriculum. Each later cloud test should name its exact coverage and cleanup evidence.
