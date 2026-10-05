#!/usr/bin/env python3
"""Inspect `terraform test -json -verbose` output; never call AWS or Kubernetes."""
import json
from pathlib import Path
import sys


def main(path):
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    summaries = [event["test_summary"] for event in events if event.get("type") == "test_summary"]
    if len(summaries) != 1 or summaries[0].get("status") != "pass":
        raise SystemExit("The complete Terraform test run must pass before checking replacement actions.")
    plans = [event["test_plan"] for event in events
             if event.get("type") == "test_plan" and event.get("@testrun") == "immutable_repairs"]
    if len(plans) != 1:
        raise SystemExit("Expected exactly one immutable_repairs test plan.")
    changes = {item["address"]: item["change"]["actions"] for item in plans[0]["resource_changes"]}
    for address in ('kubernetes_manifest.job["Job/check"]',
                    'kubernetes_manifest.storage_class["StorageClass/arcade-gp3"]'):
        if changes.get(address) != ["delete", "create"]:
            raise SystemExit(f"Expected a destroy/create replacement for {address}: {changes.get(address)}")
    if changes.get("kubernetes_manifest.namespace") != ["no-op"]:
        raise SystemExit("Immutable repairs must not replace the namespace.")
    print("PASS: Terraform planned Job and StorageClass replacements; namespace is unchanged.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: assert-replacements.py TERRAFORM_TEST_JSONL")
    main(sys.argv[1])
