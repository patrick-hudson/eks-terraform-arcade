#!/usr/bin/env python3
"""Take a read-only EKS lab snapshot for import into the local practice app."""
import argparse
import json
from pathlib import Path
import sys

from verification import LABS, Options, collect_receipt, exit_code, write_receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Exit 0: selected checks pass; 1: failed checks; 2: setup/tool error. A receipt is partial evidence, not lab completion. No resource is created, changed or deleted.")
    parser.add_argument("--lab", required=True, choices=LABS)
    parser.add_argument("--phase", choices=("verify", "cleanup"), default="verify")
    parser.add_argument("--profile", required=True, help="Sandbox AWS CLI profile; authenticate it first.")
    parser.add_argument("--expected-account", required=True, help="Sandbox account ID, checked before EKS or Kubernetes reads.")
    parser.add_argument("--region", required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--context", default="", help="Existing EKS kubeconfig context; mandatory except lab 07 cleanup.")
    parser.add_argument("--output", type=Path, help="Receipt file in an existing local directory; atomically replaces your own regular file, refuses symlinks. Without this, writes JSON to stdout.")
    args = parser.parse_args(argv)
    try:
        opts = Options(args.lab, args.phase, args.profile, args.expected_account, args.region, args.cluster, args.context)
        opts.validate()
        if args.output and args.output.is_symlink():
            raise ValueError("Receipt output must not be a symlink.")
        if args.output and not args.output.parent.is_dir():
            raise ValueError("Receipt output directory does not exist; create it first.")
        receipt = collect_receipt(opts)
        if args.output:
            write_receipt(args.output, receipt)
            counts = receipt["summary"]
            print(f"Receipt saved: {args.output}. Passed={counts['passed']}; failed={counts['failed']}; errors={counts['errors']}.", file=sys.stderr)
        else:
            print(json.dumps(receipt, indent=2))
        return exit_code(receipt)
    except (ValueError, OSError) as error:
        print(f"Verification setup error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
