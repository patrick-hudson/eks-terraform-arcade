#!/usr/bin/env python3
"""Own one deliberately unmanaged Game 06 fixture; never adopt a name collision."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


RECEIPT = Path("state-rescue-fixture.json")


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError(f"{' '.join(args[:3])} failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "{}")


def identity():
    expected = {
        "version": 1,
        "profile": os.environ.get("AWS_PROFILE", ""),
        "region": os.environ.get("TF_VAR_region", ""),
        "account": os.environ.get("TF_VAR_expected_account_id", ""),
        "lab_id": os.environ.get("TF_VAR_lab_id", ""),
    }
    if not expected["profile"] or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", expected["region"]):
        raise ValueError("Export AWS_PROFILE and TF_VAR_region before continuing.")
    if not re.fullmatch(r"\d{12}", expected["account"]):
        raise ValueError("Export the intended 12-digit TF_VAR_expected_account_id.")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,19}", expected["lab_id"]):
        raise ValueError("TF_VAR_lab_id must be 3–20 lowercase letters, digits or hyphens, starting with a letter.")
    expected["log_group"] = f"/arcade/{expected['lab_id']}/state-rescue"
    return expected


def aws(expected, *args):
    return run("aws", "--profile", expected["profile"], "--region", expected["region"],
               "--output", "json", "--no-cli-pager", *args)


def confirm_account(expected):
    if aws(expected, "sts", "get-caller-identity").get("Account") != expected["account"]:
        raise ValueError("AWS account differs from TF_VAR_expected_account_id; stopped.")


def tags(expected):
    return {"Project": "aws-interview-arcade", "Lab": "06", "LabId": expected["lab_id"], "Owner": "terraform"}


def receipt(expected):
    if RECEIPT.is_symlink() or not RECEIPT.is_file():
        raise ValueError("No successful creation receipt here. Do not import, change or delete an existing group.")
    if json.loads(RECEIPT.read_text()) != expected:
        raise ValueError("Creation receipt differs from this profile, region, account or lab name; stopped.")


def matching_groups(expected):
    response = aws(expected, "logs", "describe-log-groups", "--log-group-name-prefix", expected["log_group"])
    return [group for group in response.get("logGroups", []) if group.get("logGroupName") == expected["log_group"]]


def check_owned(expected):
    receipt(expected)
    confirm_account(expected)
    if len(matching_groups(expected)) != 1:
        raise ValueError("The exact recorded log group was not found; stopped.")
    actual = aws(expected, "logs", "list-tags-log-group", "--log-group-name", expected["log_group"]).get("tags", {})
    if any(actual.get(key) != value for key, value in tags(expected).items()):
        raise ValueError("The recorded group's ownership tags differ; stopped.")


def check_state(expected):
    state = run("terraform", "show", "-json")

    def resources(module):
        return module.get("resources", []) + [r for child in module.get("child_modules", []) for r in resources(child)]

    managed = [r for r in resources(state.get("values", {}).get("root_module", {})) if r.get("mode") == "managed"]
    if len(managed) != 1 or managed[0].get("address") not in {
        "aws_cloudwatch_log_group.app", "aws_cloudwatch_log_group.service"
    }:
        raise ValueError("State must contain only the imported Game 06 log group. Inspect state before cleanup.")
    values = managed[0].get("values", {})
    arn = values.get("arn", "").removesuffix(":*").split(":", 5)
    if (values.get("name") != expected["log_group"] or len(arn) != 6
            or arn[2:] != ["logs", expected["region"], expected["account"], "log-group:" + expected["log_group"]]):
        raise ValueError("Terraform state points at a different log group, account or region; stopped.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "name", "check", "drift", "absent"])
    parser.add_argument("--state", action="store_true", help="Also require state to own only this exact group (check only).")
    args = parser.parse_args(argv)
    if args.state and args.action != "check":
        parser.error("--state is only supported with check")
    try:
        expected = identity()
        if args.action == "create":
            if RECEIPT.exists() or RECEIPT.is_symlink():
                raise ValueError("A receipt already exists. Use check to resume; do not overwrite cleanup evidence.")
            confirm_account(expected)
            # A failed or ambiguous create grants no ownership. Never continue to retention.
            aws(expected, "logs", "create-log-group", "--log-group-name", expected["log_group"],
                "--tags", json.dumps(tags(expected)))
            # Record success before another AWS call, including a retention call that may fail.
            with RECEIPT.open("x") as stream:
                json.dump(expected, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            aws(expected, "logs", "put-retention-policy", "--log-group-name", expected["log_group"], "--retention-in-days", "1")
            print(f"Created {expected['log_group']}; keep {RECEIPT} with this workspace until teardown is verified.")
        elif args.action == "absent":
            receipt(expected)
            confirm_account(expected)
            if matching_groups(expected):
                raise ValueError("The recorded group still exists; teardown is not complete.")
            print("The exact recorded log group is absent. Keep the receipt and state backup as cleanup evidence.")
        else:
            check_owned(expected)
            if args.state:
                check_state(expected)
            if args.action == "drift":
                aws(expected, "logs", "put-retention-policy", "--log-group-name", expected["log_group"], "--retention-in-days", "7")
            elif args.action == "name":
                print(expected["log_group"])
            else:
                print("Creation receipt, AWS identity and exact log group ownership match.")
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"STOP: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
