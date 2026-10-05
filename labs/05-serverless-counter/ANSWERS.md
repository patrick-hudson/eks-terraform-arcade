# Answer — 05

The function reads `TABLE_NAME`; the incident deploys `COUNTER_TABLE`. The invocation raises `KeyError` before it calls DynamoDB. Keep IAM scoped; repair the environment contract:

```bash
cd "$LAB_ROOT/run/05-serverless-counter"
terraform plan -var='table_environment_key=TABLE_NAME' -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
aws lambda wait function-updated-v2 --function-name "$(terraform output -raw function_name)"
```

Then rerun acceptance from the mission. `source_code_hash` changes deployments when the code changes; it is not involved in this fault because the code is unchanged. CloudWatch may take several seconds to expose new logs.

Atomic `ADD` prevents lost updates under concurrency, but replaying a successful request increments again. An idempotency design needs a caller-stable operation ID and conditional state transition, not a random new ID per retry. Unit tests do not prove AWS policy evaluation or network/service availability.
