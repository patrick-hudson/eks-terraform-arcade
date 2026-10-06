#!/usr/bin/env python3
"""Prove plan-reader semantics against real built-in Terraform in a temp directory.

Unlike authored drills and unit fixtures, every JSON document here is generated
by Terraform. Local terraform_data apply creates state only; there is no cloud
provider, remote backend or provisioner. All state and plans are removed on exit.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_check import isolated_environment
from plan_review import review_plan

ROOT = Path(__file__).resolve().parents[2]


def verify():
    bundled = ROOT / ".tools/bin/terraform"
    terraform = str(bundled) if bundled.is_file() else shutil.which("terraform")
    if not terraform:
        raise RuntimeError("Terraform is required for this developer proof; run the existing tool setup first.")
    with tempfile.TemporaryDirectory(prefix="arcade-plan-proof-") as temporary:
        workspace = Path(temporary)
        env = isolated_environment(workspace)
        # The allowlisted environment has no cloud credentials, TF_VAR_*, CLI
        # config, plugins or parent Terraform state. The fixture uses only the
        # terraform.io/builtin/terraform provider shipped in the CLI binary.
        assert "AWS_ACCESS_KEY_ID" not in env
        assert "AWS_SESSION_TOKEN" not in env
        source = (ROOT / "scripts/tests/fixtures/plan-review/main.tf").read_text()
        (workspace / "main.tf").write_text(source)

        def run(*arguments):
            result = subprocess.run([terraform, *arguments], cwd=workspace, env=env,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, timeout=60)
            if result.returncode != 0:
                # Only this fixed, non-secret fixture can enter the proof output.
                raise RuntimeError("Terraform fixture command failed: " + " ".join(arguments)
                                   + "\n" + result.stdout + result.stderr)
            return result.stdout

        def saved_plan(name, *arguments):
            run("plan", "-input=false", "-no-color", "-out=" + name, *arguments)
            document = json.loads(run("show", "-json", name))
            for record in document.get("resource_changes", []):
                assert record["provider_name"] == "terraform.io/builtin/terraform"
            return document, review_plan(document)

        run("init", "-backend=false", "-input=false", "-no-color")
        version = json.loads(run("version", "-json"))["terraform_version"]
        _, created = saved_plan("create.plan")
        assert created["changes"]["actionCounts"]["create"] == 4
        run("apply", "-input=false", "-no-color", "create.plan")

        updated_json, updated = saved_plan("update.plan", "-var=input_value=changed")
        assert updated["changes"]["actionCounts"]["update"] == 1
        assert updated["changes"]["actionCounts"]["create"] == 0
        assert next(record for record in updated_json["resource_changes"]
                    if record["address"] == "terraform_data.payload")["change"]["actions"] == ["update"]

        replaced_json, replaced = saved_plan("replace.plan", "-var=replacement_key=changed")
        raw_replacements = {record["address"]: record["change"]["actions"]
                            for record in replaced_json["resource_changes"]}
        assert raw_replacements["terraform_data.delete_first"] == ["delete", "create"]
        assert raw_replacements["terraform_data.create_first"] == ["create", "delete"]
        assert replaced["changes"]["replacementCount"] == 2
        assert replaced["changes"]["actionCounts"]["create"] == 2
        assert replaced["changes"]["actionCounts"]["delete"] == 2
        orders = {row["address"]: row["replacementOrder"] for row in replaced["changes"]["resources"]}
        assert orders["terraform_data.delete_first"] == "delete-before-create"
        assert orders["terraform_data.create_first"] == "create-before-delete"

        renamed_source = source.replace('"terraform_data" "legacy"', '"terraform_data" "renamed"')
        (workspace / "main.tf").write_text(renamed_source)
        _, renamed = saved_plan("rename.plan")
        assert renamed["changes"]["actionCounts"]["delete"] == 1
        assert renamed["changes"]["actionCounts"]["create"] == 1
        assert renamed["changes"]["moveCount"] == 0

        (workspace / "main.tf").write_text(renamed_source + "\nmoved {\n  from = terraform_data.legacy\n  to = terraform_data.renamed\n}\n")
        moved_json, moved = saved_plan("move.plan")
        raw_move = next(record for record in moved_json["resource_changes"]
                        if record["address"] == "terraform_data.renamed")
        assert raw_move["previous_address"] == "terraform_data.legacy"
        assert raw_move["change"]["actions"] == ["no-op"]
        assert moved["changes"]["moveCount"] == 1
        assert moved["changes"]["actionCounts"]["no-op"] == 4
        assert moved["changes"]["actionCounts"]["create"] == 0
        assert moved["changes"]["actionCounts"]["delete"] == 0
        print(f"PASS: Terraform {version} generated create, update, both replacement orders, rename and move plans.")
        print("Provider: terraform.io/builtin/terraform. Isolated temporary state; cloud credentials unavailable; no AWS resources created.")


if __name__ == "__main__":
    try:
        verify()
    except (AssertionError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print("FAIL: genuine Terraform plan proof: " + str(error), file=sys.stderr)
        raise SystemExit(1)
