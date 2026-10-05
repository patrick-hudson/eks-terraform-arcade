# Hints — 05

1. Start with the response body and function logs, not policy edits.
2. Does the error occur before any SDK request? Compare the deployed environment to the handler's runtime contract.
3. A Terraform apply validates the resource configuration, not your Python program's assumptions about environment-variable names.
