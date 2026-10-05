# 05 — The green deployment that fails at runtime

**45–60 minutes · Lambda + DynamoDB + IAM + logs · target <$0.10 · broken start.** No API Gateway, function URL, VPC attachment or paid idle compute. Invoke at most ten times; no infinite load generator. Costs are request/storage/log based and depend on your account and region.

## Assignment

Build an atomic counter that returns `{statusCode: 200, counter, visits}`. Only the named table is writable by the function. Logs expire after one day. The deployment is green, but the first invocation fails. Determine whether the problem is runtime configuration, IAM, packaging, or DynamoDB schema. Do not grant broader permissions without evidence.

For build mode, implement `starter/TASKS.md`. For incident mode, run the reference architecture with its faulty configuration:

```bash
mkdir -p "$LAB_ROOT/run/05-serverless-counter"
cp "$LAB_ROOT/labs/05-serverless-counter/solution/"*.tf "$LAB_ROOT/run/05-serverless-counter/"
cp "$LAB_ROOT/labs/05-serverless-counter/solution/"*.py "$LAB_ROOT/run/05-serverless-counter/"
cp "$LAB_ROOT/labs/05-serverless-counter/solution/.terraform.lock.hcl" "$LAB_ROOT/run/05-serverless-counter/"
cd "$LAB_ROOT/run/05-serverless-counter"
python3 -m unittest -v
terraform init
terraform validate
terraform plan -var='table_environment_key=COUNTER_TABLE' -out=apply.tfplan
terraform show apply.tfplan
terraform apply apply.tfplan
FUNCTION=$(terraform output -raw function_name)
aws lambda wait function-active-v2 --function-name "$FUNCTION"
aws lambda invoke --function-name "$FUNCTION" --cli-binary-format raw-in-base64-out \
  --payload '{"counter":"interview"}' response.json
cat response.json
```

A successful CLI transport (`StatusCode: 200`) can still contain `FunctionError`. Distinguish Lambda Invoke's status from your handler's `statusCode` field.

```bash
aws logs tail "$(terraform output -raw log_group)" --since 10m
aws lambda get-function-configuration --function-name "$FUNCTION" \
  --query '{Runtime:Runtime,Handler:Handler,Environment:Environment,LastUpdateStatus:LastUpdateStatus}'
terraform state show aws_lambda_function.counter
```

Explain the evidence, then fix the configuration in Terraform. [Hints](HINTS.md) and [answer](ANSWERS.md) are separate.

## Acceptance and senior extension

After repair, invoke twice with `counter=interview`: the returned values increase by one. Verify the stored item with a strongly consistent read:

```bash
aws lambda invoke --function-name "$FUNCTION" --cli-binary-format raw-in-base64-out \
  --payload '{"counter":"interview"}' response.json
cat response.json
aws lambda invoke --function-name "$FUNCTION" --cli-binary-format raw-in-base64-out \
  --payload '{"counter":"interview"}' response.json
cat response.json
aws dynamodb get-item --table-name "$(terraform output -raw table_name)" \
  --key '{"pk":{"S":"interview"}}' --consistent-read
aws lambda invoke --function-name "$FUNCTION" --cli-binary-format raw-in-base64-out \
  --payload '{"counter":"NOT-VALID"}' response.json
cat response.json
terraform plan
```

Invalid input returns 400 and must not write. The operator needs `dynamodb:GetItem`; the function role intentionally does not. Local tests check input validation/configuration and response decoding; live AWS proves IAM and atomic increments.

Senior extension: why is an atomic counter not idempotent? Design a transaction containing an idempotency token with a conditional write and the increment. Discuss retry windows, TTL (not immediate deletion), write contention, throttling, and cost. Do not claim exactly-once behavior from this reference implementation. How would you pin/package boto3 for reproducible production releases rather than use Lambda's bundled SDK?

## Teardown, including the broken deployment

```bash
FUNCTION=$(terraform output -raw function_name)
TABLE=$(terraform output -raw table_name)
LOG_GROUP=$(terraform output -raw log_group)
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
aws dynamodb wait table-not-exists --table-name "$TABLE"
aws lambda get-function --function-name "$FUNCTION"
aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
  --query 'logGroups[].logGroupName'
```

Expect empty state, the waiter to succeed, Lambda `ResourceNotFoundException`, and no exact log-group match. No function invocations after destroy starts.

Sources: [Python Lambda handler](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html), [DynamoDB atomic counters](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html#WorkingWithItems.AtomicCounters), [Lambda Invoke response](https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html).
