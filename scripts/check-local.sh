#!/usr/bin/env bash
# No apply/destroy or AWS CLI calls. Terraform init downloads provider binaries.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
command -v terraform >/dev/null
terraform fmt -check -recursive "$ROOT/labs"
while IFS= read -r directory; do
  printf '\nValidating %s\n' "$directory"
  terraform -chdir="$directory" init -backend=false -input=false
  terraform -chdir="$directory" validate
# Each directory containing solution .tf files is a runnable root.
done < <(find "$ROOT/labs" -name '*.tf' -path '*/solution/*' -exec dirname {} \; | sort -u)
python3 -m unittest discover -s "$ROOT/labs/05-serverless-counter/solution" -p 'test_*.py' -v
