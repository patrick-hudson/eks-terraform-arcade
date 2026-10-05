#!/usr/bin/env bash
# Source this file once per lab terminal. It never selects an AWS profile.
if [ -z "${BASH_VERSION:-}" ]; then
  printf 'Use Bash to source scripts/env.sh.\n' >&2
  return 1 2>/dev/null || exit 1
fi
export LAB_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
case ":$PATH:" in
  *":$LAB_ROOT/.tools/bin:"*) ;;
  *) export PATH="$LAB_ROOT/.tools/bin:$PATH" ;;
esac
export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"
export AWS_PAGER="${AWS_PAGER-}"
export TF_VAR_region="${TF_VAR_region:-$AWS_REGION}"
export TF_VAR_lab_id="${TF_VAR_lab_id:-tfeks}"
export LAB_KUBE_CONTEXT="${LAB_KUBE_CONTEXT:-arcade-lab}"
