# Build contract

Write a Python handler plus Terraform for one PAY_PER_REQUEST DynamoDB table keyed by string pk, one Lambda role, inline UpdateItem permission for that table, one log group with one-day retention, and a 256MiB Python3.14 function with a fifteen-second timeout. Zip handler.py with archive_file. No public endpoint. The memory and timeout allow SDK startup; they do not repair the intended environment-key fault.

Handler: reject malformed counter keys, atomically ADD 1 to visits, return the value. Write tests for invalid inputs, missing configuration, and decoding the response. Keep atomicity versus idempotency explicit.

The deployment must retain all resources in Terraform state and support destruction after a failed invocation.
