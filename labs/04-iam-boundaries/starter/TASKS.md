# Build contract

Copy `solution/versions.tf` into your own run directory. Write the rest without opening main.tf:
- A permissions boundary permits GetObject only beneath a synthetic bucket's published/ prefix.
- A Lambda-trusted role attaches that boundary.
- An inline read policy initially targets the wrong S3 resource type; prove the failure with the simulator, then fix it.
- Output role ARN/name, bucket ARN, and boundary ARN. No real bucket or Lambda required.

Compare to the solution only after recording your predicted decisions for all four acceptance cases.
