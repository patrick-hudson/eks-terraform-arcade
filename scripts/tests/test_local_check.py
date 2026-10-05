"""Exercise local rehearsal through the real CLI in disposable workspaces."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_check

ROOT = Path(__file__).resolve().parents[2]
TERRAFORM = shutil.which("terraform") or str(ROOT / ".tools/bin/terraform")


class LocalRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade local rehearsal ")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "learner"
        self.workspace.mkdir()

    def copy_files(self, lab, variant, names):
        for name in names:
            shutil.copyfile(ROOT / "labs" / lab / variant / name, self.workspace / name)

    def invoke(self, lab, *extra, env=None):
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/local-check.py"), lab,
             "--workspace", str(self.workspace), "--json", *extra],
            capture_output=True, text=True, timeout=30, env=environment,
        )

    def test_counter_passes_without_touching_learner_files_or_using_learner_tests(self):
        self.copy_files("05-serverless-counter", "solution", ["handler.py"])
        (self.workspace / "terraform.tfstate").write_text("STATE MUST STAY HERE")
        (self.workspace / "test_handler.py").write_text("raise RuntimeError('untrusted learner test')")
        before = {p.name: p.read_bytes() for p in self.workspace.iterdir()}
        result = self.invoke("05")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "passed")
        self.assertIn("Ran 3 tests", report["checks"][0]["output"])
        self.assertIn("IAM", report["limits"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.workspace.iterdir()})

    def test_counter_bad_handler_fails_the_trusted_tests(self):
        (self.workspace / "handler.py").write_text("def lambda_handler(event, context):\n    return {'statusCode': 200}\n")
        result = self.invoke("05")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")

    def test_counter_cannot_inherit_aws_credentials_or_pythonpath(self):
        self.copy_files("05-serverless-counter", "solution", ["handler.py"])
        handler = self.workspace / "handler.py"
        handler.write_text("import os\nassert 'AWS_ACCESS_KEY_ID' not in os.environ\n"
                           "assert 'AWS_SESSION_TOKEN' not in os.environ\n"
                           "assert 'PYTHONPATH' not in os.environ\n"
                           "assert 'TF_VAR_secret' not in os.environ\n" + handler.read_text())
        result = self.invoke("05", env={"AWS_ACCESS_KEY_ID": "do-not-inherit", "AWS_SESSION_TOKEN": "do-not-inherit", "TF_VAR_secret": "do-not-inherit", "PYTHONPATH": "/missing"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("do-not-inherit", result.stdout)

    def test_missing_file_is_a_setup_error_with_a_useful_message(self):
        result = self.invoke("05")
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "setup-error")
        self.assertIn("handler.py", report["message"])

    def test_symlink_workspace_file_and_parent_are_rejected(self):
        source = ROOT / "labs/05-serverless-counter/solution/handler.py"
        (self.workspace / "handler.py").symlink_to(source)
        self.assertEqual(self.invoke("05").returncode, 2)
        (self.workspace / "handler.py").unlink()
        self.copy_files("05-serverless-counter", "solution", ["handler.py"])
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        self.workspace = alias
        self.assertEqual(self.invoke("05").returncode, 2)

    def test_named_pipe_is_rejected_without_blocking(self):
        os.mkfifo(self.workspace / "handler.py")
        result = self.invoke("05")
        self.assertEqual(result.returncode, 2)
        self.assertIn("regular file", json.loads(result.stdout)["message"])

    def test_oversized_source_file_is_rejected(self):
        (self.workspace / "handler.py").write_bytes(b"x" * (local_check.MAX_FILE_BYTES + 1))
        result = self.invoke("05")
        self.assertEqual(result.returncode, 2)
        self.assertIn("too large", json.loads(result.stdout)["message"])

    def test_missing_terraform_is_a_setup_error(self):
        self.copy_files("00-terraform-contracts", "solution", ["main.tf", "variables.tf"])
        result = self.invoke("00", env={"PATH": "/nonexistent"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Terraform was not found", json.loads(result.stdout)["message"])

    @unittest.skipUnless(Path(TERRAFORM).is_file(), "Terraform is needed to prepare the test command")
    def test_trusted_contracts_must_explicitly_be_plan_only(self):
        fake_root = Path(self.temp.name) / "repo"
        contracts = fake_root / "labs/00-terraform-contracts/solution/tests/contracts.tftest.hcl"
        contracts.parent.mkdir(parents=True)
        for declaration in ('command = apply', ''):
            contracts.write_text('run "must_not_apply" {\n' + declaration + '\n}\n')
            with patch.dict(os.environ, {"PATH": str(Path(TERRAFORM).parent)}):
                with tempfile.TemporaryDirectory(dir=self.temp.name) as target:
                    temp = Path(target)
                    env = local_check.isolated_environment(temp)
                    with self.assertRaisesRegex(local_check.SetupError, "command = plan"):
                        local_check.commands_for("00", fake_root, temp, env)

    def test_output_limit_stops_a_noisy_program(self):
        result = local_check.run_bounded(
            [sys.executable, "-c", "while True: print('x' * 4096, flush=True)"],
            self.workspace, {}, timeout=3, output_limit=1024,
        )
        self.assertEqual(result["stopReason"], "output-limit")
        self.assertLessEqual(len(result["output"].encode()), 1024)

    def test_timeout_stops_a_program_that_does_not_finish(self):
        result = local_check.run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            self.workspace, {}, timeout=0.1,
        )
        self.assertEqual(result["stopReason"], "timeout")

    def test_default_workspace_is_the_canonical_lab_directory(self):
        self.assertEqual(local_check.default_workspace(ROOT, "00"), ROOT / "run/00-contracts")
        self.assertEqual(local_check.default_workspace(ROOT, "05"), ROOT / "run/05-serverless-counter")

    @unittest.skipUnless(Path(TERRAFORM).is_file(), "Terraform is needed for the real contract rehearsal")
    def test_terraform_starter_fails_solution_passes_and_wrong_worker_value_fails(self):
        self.copy_files("00-terraform-contracts", "starter", ["main.tf", "variables.tf"])
        (self.workspace / "terraform.tfstate").write_text("NOT JSON AND MUST NOT BE READ")
        (self.workspace / "tests").mkdir()
        (self.workspace / "tests/evil.tftest.hcl").write_text("run \"never_run\" { command = apply }")
        env = {"PATH": str(Path(TERRAFORM).parent) + os.pathsep + os.environ.get("PATH", "")}
        broken = self.invoke("00", env=env)
        self.assertEqual(broken.returncode, 1, broken.stdout)
        self.assertIn("Invalid for_each argument", broken.stdout)
        self.copy_files("00-terraform-contracts", "solution", ["main.tf", "variables.tf"])
        before = {str(p.relative_to(self.workspace)): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}
        fixed = self.invoke("00", env=env)
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
        self.assertIn("8 passed, 0 failed", fixed.stdout)
        self.assertEqual(before, {str(p.relative_to(self.workspace)): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()})
        main = self.workspace / "main.tf"
        main.write_text(main.read_text().replace("input    = each.value", 'input    = merge(each.value, { memory_mib = each.key == "worker" ? 999 : each.value.memory_mib })'))
        mutated = self.invoke("00", env=env)
        self.assertEqual(mutated.returncode, 1, mutated.stdout)
        self.assertIn("2 failed", mutated.stdout)


if __name__ == "__main__":
    unittest.main()
