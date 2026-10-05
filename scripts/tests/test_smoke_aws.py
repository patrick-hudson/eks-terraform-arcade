"""Offline contract tests. Fake command responses are not live AWS validation."""
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("smoke_aws", Path(__file__).parents[1] / "smoke_aws.py")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
SOURCE = Path(__file__).parents[2] / "labs/05-serverless-counter/solution"


def plan_fixture(lab_id, mode="create"):
    names = {
        "aws_dynamodb_table.counter": {"name": f"{lab_id}-05-counter", "billing_mode": "PAY_PER_REQUEST"},
        "aws_cloudwatch_log_group.counter": {"name": f"/aws/lambda/{lab_id}-05-counter", "retention_in_days": 1},
        "aws_iam_role.lambda": {"name": f"{lab_id}-05-lambda"},
        "aws_iam_role_policy.lambda": {"name": f"{lab_id}-05-policy", "role": f"{lab_id}-05-lambda"},
        "aws_lambda_function.counter": {"function_name": f"{lab_id}-05-counter", "memory_size": 256, "timeout": 15, "environment": [{"variables": {"COUNTER_TABLE": f"{lab_id}-05-counter"}}]},
    }
    changes = []
    for address, after in names.items():
        action = {"create": ["create"], "destroy": ["delete"], "repair": ["no-op"], "verify": ["no-op"]}[mode]
        before = dict(after)
        if mode in {"repair", "verify"} and address == "aws_lambda_function.counter":
            action = ["update"] if mode == "repair" else ["no-op"]
            after = {**after, "environment": [{"variables": {"TABLE_NAME": f"{lab_id}-05-counter"}}]}
        changes.append({"address": address, "mode": "managed", "type": address.split(".")[0], "change": {"actions": action, "before": None if mode == "create" else before, "after": None if mode == "destroy" else after}})
    return {"resource_changes": changes}


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.phase = "create"
        self.visits = 0
        self.resources = False
        self.broken = True
        self.access_denied = False
        self.interrupt = False
        self.invalid_write = False
        self.account = "123456789012"

    def __call__(self, args, cwd, env):
        self.calls.append(args)
        result, code, error = {}, 0, ""
        manifest = json.loads((cwd / "run.json").read_text())
        lab = manifest["lab_id"]
        if args[0] == "terraform":
            operation = args[1]
            if operation == "plan":
                self.phase = "destroy" if "-destroy" in args else "verify" if "-out=verify.tfplan" in args else "repair" if "-var=table_environment_key=TABLE_NAME" in args else "create"
                destination = next(x[5:] for x in args if x.startswith("-out="))
                (cwd / destination).write_text(self.phase)
            if operation == "show":
                result = plan_fixture(lab, self.phase)
            if operation == "apply":
                phase = (cwd / args[-1]).read_text()
                self.resources = phase != "destroy"
                if phase == "repair":
                    self.broken = False
                if self.interrupt and phase == "create":
                    self.interrupt = False
                    raise KeyboardInterrupt()
            if operation == "state":
                return subprocess.CompletedProcess(args, 0, "aws_lambda_function.counter\n" if self.resources else "", "")
        else:
            if "get-caller-identity" in args:
                result = {"Account": self.account, "Arn": "arn:aws:iam::123456789012:role/sandbox"}
            elif "invoke" in args:
                request = json.loads(args[args.index("--payload") + 1])
                if self.broken:
                    result = {"StatusCode": 200, "FunctionError": "Unhandled"}
                    response = {"errorType": "KeyError", "errorMessage": "'TABLE_NAME'"}
                elif request["counter"] == "NOT-VALID":
                    result = {"StatusCode": 200}
                    response = {"statusCode": 400}
                else:
                    self.visits += 1
                    result = {"StatusCode": 200}
                    response = {"statusCode": 200, "counter": "smoke", "visits": self.visits}
                (cwd / args[-1]).write_text(json.dumps(response))
            elif "get-item" in args:
                key = json.loads(args[args.index("--key") + 1])["pk"]["S"]
                result = {"Item": {"pk": {"S": key}, "visits": {"N": str(self.visits)}}} if key == "smoke" or self.invalid_write else {}
                if not result:
                    return subprocess.CompletedProcess(args, 0, "", "")
            elif "describe-log-groups" in args:
                result = {"logGroups": [{"logGroupName": f"/aws/lambda/{lab}-05-counter"}]} if self.resources else {"logGroups": []}
            elif any(name in args for name in ("get-function", "describe-table", "get-role")):
                if not self.resources:
                    code = 254
                    error = "An error occurred (AccessDeniedException)" if self.access_denied else "An error occurred (NoSuchEntity)" if "get-role" in args else "An error occurred (ResourceNotFoundException)"
        return subprocess.CompletedProcess(args, code, json.dumps(result), error)


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade smoke ")
        self.root = Path(self.temp.name)
        target = self.root / "labs/05-serverless-counter/solution"
        target.mkdir(parents=True)
        for name in ("main.tf", "versions.tf", "handler.py", ".terraform.lock.hcl"):
            (target / name).write_bytes((SOURCE / name).read_bytes())
        self.path = smoke.prepare(self.root, "arcade-smoke", "123456789012", "us-west-2")
        self.runner = FakeRunner()
        self.run = smoke.SmokeRun(self.root, self.path, self.runner)

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_is_local_and_records_identity_and_source_hashes(self):
        manifest = json.loads((self.path / "run.json").read_text())
        self.assertEqual(manifest["status"], "prepared")
        self.assertEqual(manifest["account_id"], "123456789012")
        self.assertEqual(len(manifest["source_hashes"]), 5)
        self.assertEqual(manifest["region"], "us-west-2")
        self.assertFalse((self.path / "initial.tfplan").exists())
        self.assertEqual(shlex.split(manifest["recovery_command"]), ["python3", str(self.root / "scripts/smoke-aws.py"), "cleanup", "--run-dir", str(self.path), "--execute"])

    def test_printed_followup_commands_use_absolute_shell_quoted_paths(self):
        output = io.StringIO()
        with patch.object(smoke, "prepare", return_value=self.path), redirect_stdout(output):
            result = smoke.main(["prepare", "--profile", "arcade-smoke", "--account-id", "123456789012", "--region", "us-west-2"])
        self.assertEqual(result, 0)
        command = shlex.split(output.getvalue().split("Next: ", 1)[1].strip())
        self.assertTrue(Path(command[1]).is_absolute())
        self.assertEqual(command[command.index("--run-dir") + 1], str(self.path))
        output = io.StringIO()
        with patch.object(smoke, "SmokeRun", return_value=self.run), redirect_stdout(output):
            result = smoke.main(["run", "--run-dir", str(self.path)])
        self.assertEqual(result, 0)
        command = shlex.split(output.getvalue().split("After review: ", 1)[1].strip())
        self.assertTrue(Path(command[1]).is_absolute())
        self.assertEqual(command[command.index("--run-dir") + 1], str(self.path))

    def test_plan_is_read_only_and_execute_requires_exact_digest(self):
        digest = self.run.plan()
        self.assertEqual(len(digest), 64)
        self.assertFalse(any("apply" in c for c in self.runner.calls))
        with self.assertRaises(smoke.SmokeError):
            self.run.execute("0" * 64)
        self.assertFalse(any("apply" in c for c in self.runner.calls))

    def test_wrong_account_is_rejected_before_terraform(self):
        self.runner.account = "999999999999"
        with self.assertRaises(smoke.SmokeError):
            self.run.plan()
        self.assertFalse(any(c[0] == "terraform" for c in self.runner.calls))

    def test_tampered_sources_or_plan_are_rejected(self):
        digest = self.run.plan()
        (self.path / "main.tf").write_text("changed")
        with self.assertRaises(smoke.SmokeError):
            self.run.execute(digest)
        self.assertFalse(any("apply" in c for c in self.runner.calls))

    def test_tampered_plan_binary_is_rejected(self):
        approval = self.run.plan()
        (self.path / "initial.tfplan").write_text("replaced plan")
        with self.assertRaises(smoke.SmokeError):
            self.run.execute(approval)
        self.assertFalse(any("apply" in c for c in self.runner.calls))

    def test_extra_billable_resource_and_replace_action_are_rejected(self):
        for extra in ("aws_nat_gateway.bad", "aws_lambda_function.extra"):
            plan = plan_fixture(self.path.name)
            plan["resource_changes"].append({"address": extra, "mode": "managed", "change": {"actions": ["create"], "after": {}}})
            with self.assertRaises(smoke.SmokeError):
                smoke.validate_plan(plan, self.path.name, "create")
        plan = plan_fixture(self.path.name)
        plan["resource_changes"][0]["change"]["actions"] = ["delete", "create"]
        with self.assertRaises(smoke.SmokeError):
            smoke.validate_plan(plan, self.path.name, "create")

    def test_destroy_cannot_delete_resources_with_foreign_names(self):
        cases = ((0, "name"), (1, "name"), (2, "name"), (3, "name"), (3, "role"), (4, "function_name"))
        for index, key in cases:
            with self.subTest(resource=index, key=key):
                plan = plan_fixture(self.path.name, "destroy")
                plan["resource_changes"][index]["change"]["before"][key] = "somebody-elses-resource"
                with self.assertRaises(smoke.SmokeError):
                    smoke.validate_plan(plan, self.path.name, "destroy")

    def test_lambda_startup_headroom_requires_exact_reviewed_limits(self):
        for mode in ("create", "repair", "verify"):
            with self.subTest(mode=mode):
                plan = plan_fixture(self.path.name, mode)
                self.assertEqual(len(smoke.validate_plan(plan, self.path.name, mode)), 5)
                for memory, timeout in ((128, 15), (256, 5), (512, 15), (256, 30)):
                    with self.subTest(memory=memory, timeout=timeout):
                        changed = plan_fixture(self.path.name, mode)
                        function = next(resource for resource in changed["resource_changes"] if resource["address"] == "aws_lambda_function.counter")
                        function["change"]["after"].update(memory_size=memory, timeout=timeout)
                        with self.assertRaises(smoke.SmokeError):
                            smoke.validate_plan(changed, self.path.name, mode)

    def test_successful_missing_item_cli_output_is_an_empty_item_result(self):
        for output in ("", " \n", "{}", '{"Item":{"visits":{"N":"2"}}}'):
            with self.subTest(output=output):
                response = subprocess.CompletedProcess([], 0, output, "")
                with patch.object(self.run, "aws", return_value=response):
                    self.assertEqual(self.run.stored_item("smoke"), json.loads(output) if output.strip() else {})

    def test_malformed_item_output_is_not_treated_as_absence(self):
        with patch.object(self.run, "aws", return_value=subprocess.CompletedProcess([], 0, "not-json", "")):
            with self.assertRaises(json.JSONDecodeError):
                self.run.stored_item("smoke")

    def test_happy_path_proves_fault_repair_counter_and_named_absence(self):
        self.run.execute(self.run.plan())
        report = json.loads((self.path / "run.json").read_text())
        self.assertEqual(report["status"], "passed-cleaned")
        self.assertEqual(report["checks"]["increments"], [1, 2])
        self.assertTrue(report["checks"]["invalid_input_did_not_write"])
        self.assertTrue(report["checks"]["converged"])
        self.assertEqual(report["checks"]["absence"], ["lambda", "dynamodb", "iam_role", "log_group"])
        self.assertFalse(self.runner.resources)
        self.assertTrue((self.path / "initial.tfplan").exists())
        for args in self.runner.calls:
            if args[0] == "aws":
                self.assertEqual(args[args.index("--profile") + 1], "arcade-smoke")

    def test_interrupt_during_apply_still_attempts_cleanup(self):
        self.runner.interrupt = True
        with self.assertRaises(KeyboardInterrupt):
            self.run.execute(self.run.plan())
        self.assertFalse(self.runner.resources)
        self.assertEqual(json.loads((self.path / "run.json").read_text())["status"], "failed-cleaned")

    def test_invalid_input_cannot_create_an_unobserved_second_item(self):
        self.runner.invalid_write = True
        with self.assertRaisesRegex(smoke.SmokeError, "Invalid input"):
            self.run.execute(self.run.plan())
        self.assertFalse(self.runner.resources)

    def test_interrupt_followed_by_cleanup_failure_preserves_both_errors(self):
        self.runner.interrupt = True
        self.runner.access_denied = True
        with self.assertRaisesRegex(smoke.SmokeError, "Cleanup failed"):
            self.run.execute(self.run.plan())
        report = json.loads((self.path / "run.json").read_text())
        self.assertEqual(report["status"], "cleanup-failed")
        self.assertIn("KeyboardInterrupt", report["error"])
        self.assertIn("AccessDenied", report["cleanup_error"])

    def test_access_denied_is_not_treated_as_absent(self):
        self.runner.access_denied = True
        with self.assertRaises(smoke.SmokeError):
            self.run.execute(self.run.plan())
        report = json.loads((self.path / "run.json").read_text())
        self.assertEqual(report["status"], "cleanup-failed")
        self.assertIn("AccessDenied", report["cleanup_error"])
        self.assertIn("cleanup --run-dir", report["recovery_command"])

    def test_cleanup_failure_is_a_nonzero_cli_exit(self):
        approval = self.run.plan()
        self.runner.access_denied = True
        with patch.object(smoke, "SmokeRun", return_value=self.run):
            self.assertEqual(smoke.main(["run", "--run-dir", str(self.path), "--execute", "--approve-plan", approval]), 1)

    def test_recovery_after_cleanup_failure_checks_absence_again(self):
        self.runner.access_denied = True
        with self.assertRaises(smoke.SmokeError):
            self.run.execute(self.run.plan())
        self.runner.access_denied = False
        self.run.cleanup()
        self.assertEqual(json.loads((self.path / "run.json").read_text())["status"], "recovered-cleaned")

    def test_stale_or_reused_runs_cannot_create_again(self):
        self.run.execute(self.run.plan())
        with self.assertRaises(smoke.SmokeError):
            self.run.plan()
        with self.assertRaises(smoke.SmokeError):
            self.run.execute("0" * 64)

    def test_run_directory_and_identity_validation(self):
        for account in ("123", "123456789012;echo"):
            with self.assertRaises(smoke.SmokeError):
                smoke.prepare(self.root, "arcade-smoke", account, "us-east-1")
        with self.assertRaises(smoke.SmokeError):
            smoke.SmokeRun(self.root, self.root / "outside", self.runner)


if __name__ == "__main__":
    unittest.main()
