"""Local launcher contracts use disposable roots; no AWS or existing run state."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab_manager as manager


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade launcher ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for variant, content in (("starter", "broken"), ("solution", "guided")):
            source = self.root / "labs/05-counter" / variant
            source.mkdir(parents=True)
            (source / "main.tf").write_text(content)
            (source / ".terraform.lock.hcl").write_text("provider lock")
        self.recipe = {
            "id": "05-counter", "alias": "05", "title": "Counter", "kind": "terraform",
            "runDirectory": "counter", "prerequisites": [], "cost": "Less than $1 for a short session",
            "modes": {mode: {"label": mode, "description": "Practice " + mode,
                "files": [{"source": f"labs/05-counter/{source}/main.tf", "destination": "main.tf"},
                          {"source": f"labs/05-counter/{source}/.terraform.lock.hcl", "destination": ".terraform.lock.hcl"}],
                "steps": [{"title": "Review", "command": "terraform plan"}],
                "cleanup": [{"title": "Remove resources", "command": "terraform destroy"}]}
                for mode, source in (("starter", "starter"), ("guided", "solution"))}}
        self.write_catalog()

    def write_catalog(self, recipes=None):
        (self.root / "lab-recipes.json").write_text(json.dumps({"schemaVersion": 1, "recipes": recipes or [self.recipe]}))

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = manager.main(list(args), root=self.root)
        return code, output.getvalue()

    def prepare(self, mode="starter"):
        code, output = self.run_cli("start", "05", "--mode", mode)
        self.assertEqual(code, 0, output)
        return self.root / "run/counter"

    def test_prepare_copies_only_recipe_files_and_prints_commands_without_execution(self):
        self.recipe["modes"]["starter"]["steps"][0]["command"] = "touch SHOULD_NOT_EXIST"
        self.write_catalog()
        code, output = self.run_cli("start", "05")
        self.assertEqual(code, 0, output)
        dest = self.root / "run/counter"
        self.assertEqual((dest / "main.tf").read_text(), "broken")
        self.assertEqual({p.name for p in dest.iterdir()}, {"main.tf", ".terraform.lock.hcl", ".arcade-session.json"})
        receipt = json.loads((dest / ".arcade-session.json").read_text())
        self.assertEqual(receipt["labId"], "05-counter")
        self.assertEqual(receipt["mode"], "starter")
        self.assertEqual(len(receipt["sourceHashes"]), 2)
        self.assertIn("touch SHOULD_NOT_EXIST", output)
        self.assertIn("terraform destroy", output)
        self.assertFalse((dest / "SHOULD_NOT_EXIST").exists())

    def test_resume_preserves_changes_state_and_guided_mode_without_explicit_mode(self):
        dest = self.prepare("guided")
        (dest / "main.tf").write_text("learner changes")
        (dest / "terraform.tfstate").write_text("existing state")
        receipt = (dest / ".arcade-session.json").read_bytes()
        code, output = self.run_cli("start", "05-counter")
        self.assertEqual(code, 0, output)
        self.assertIn("Resuming", output)
        self.assertEqual((dest / "main.tf").read_text(), "learner changes")
        self.assertEqual((dest / "terraform.tfstate").read_text(), "existing state")
        self.assertEqual((dest / ".arcade-session.json").read_bytes(), receipt)
        code, output = self.run_cli("start", "05", "--mode", "starter")
        self.assertEqual(code, 2)
        self.assertIn("mode", output)

    def test_unregistered_directory_and_wrong_receipt_are_never_adopted(self):
        dest = self.root / "run/counter"
        dest.mkdir(parents=True)
        (dest / "main.tf").write_text("mine")
        for receipt in (None, {"schemaVersion": 1, "labId": "another-lab", "mode": "starter"}):
            if receipt:
                (dest / ".arcade-session.json").write_text(json.dumps(receipt))
            code, output = self.run_cli("start", "05")
            self.assertEqual(code, 2, output)
            self.assertEqual((dest / "main.tf").read_text(), "mine")

    def test_catalog_rejects_traversal_sources_state_and_destination_collision(self):
        original = json.loads(json.dumps(self.recipe))
        cases = [
            ("source", "../outside/main.tf"), ("source", "run/existing/main.tf"),
            ("source", "labs/05-counter/starter/terraform.tfstate"),
            ("destination", "../outside.tf"), ("destination", ".terraform/cache"),
            ("destination", ".arcade-session.json"), ("destination", "terraform.tfstate"),
        ]
        for key, value in cases:
            self.recipe = json.loads(json.dumps(original))
            self.recipe["modes"]["starter"]["files"][0][key] = value
            self.write_catalog()
            code, output = self.run_cli("start", "05")
            self.assertEqual(code, 2, (key, value, output))
            self.assertFalse((self.root / "run/counter").exists())
        self.recipe = original
        self.recipe["modes"]["starter"]["files"][1]["destination"] = "main.tf"
        self.write_catalog()
        self.assertEqual(self.run_cli("start", "05")[0], 2)

    def test_symlink_source_run_parent_and_receipt_are_rejected(self):
        source = self.root / "labs/05-counter/starter/main.tf"
        source.unlink()
        source.symlink_to(self.root / "labs/05-counter/solution/main.tf")
        self.assertEqual(self.run_cli("start", "05")[0], 2)
        source.unlink()
        source.write_text("broken")
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "run").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.run_cli("start", "05")[0], 2)
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "run").unlink()
        dest = self.prepare()
        (dest / ".arcade-session.json").rename(self.root / "receipt.json")
        (dest / ".arcade-session.json").symlink_to(self.root / "receipt.json")
        self.assertEqual(self.run_cli("start", "05")[0], 2)

    def test_copy_failure_never_publishes_partial_workspace(self):
        with patch.object(manager, "copy_source", side_effect=OSError("disk full")):
            code, output = self.run_cli("start", "05")
        self.assertEqual(code, 2, output)
        self.assertFalse((self.root / "run/counter").exists())
        self.assertEqual(list((self.root / "run").iterdir()), [])

    def test_atomic_publish_refuses_even_an_existing_empty_directory(self):
        stage = self.root / "stage"
        dest = self.root / "destination"
        stage.mkdir()
        dest.mkdir()
        (stage / "data").write_text("staged")
        with self.assertRaises(FileExistsError):
            manager.publish_directory(stage, dest)
        self.assertEqual(list(dest.iterdir()), [])
        self.assertTrue((stage / "data").exists())

    def test_next_requires_preparation_and_runbook_has_no_workspace(self):
        code, output = self.run_cli("next", "05")
        self.assertEqual(code, 2)
        self.assertIn("arcade start 05", output)
        book = {**self.recipe, "id": "12-capstone", "alias": "12", "kind": "runbook", "runDirectory": None, "modes": {}}
        self.write_catalog([book])
        code, output = self.run_cli("start", "12")
        self.assertEqual(code, 0, output)
        self.assertIn("runbook", output.lower())
        self.assertFalse((self.root / "run").exists())

    def test_start_and_next_show_prerequisite_setup_order_and_commands(self):
        foundation = json.loads(json.dumps(self.recipe))
        foundation.update(id="07-foundation", alias="07", title="Cluster foundation", runDirectory="foundation")
        workload = json.loads(json.dumps(self.recipe))
        workload.update(id="08-workload", alias="08", title="Cluster workload", runDirectory="workload",
                        prerequisites=[foundation["id"]])
        self.recipe["prerequisites"] = [workload["id"], foundation["id"]]
        self.write_catalog([self.recipe, workload, foundation])
        for command in ("start", "next"):
            code, output = self.run_cli(command, "05")
            self.assertEqual(code, 0, output)
            self.assertIn("Prerequisite Terraform setup order", output)
            self.assertLess(output.index("1. 07"), output.index("2. 08"))
            self.assertEqual(output.count("start 07"), 1)
            self.assertIn("start 08", output)
            self.assertIn("not verified live readiness", output)
            self.assertFalse((self.root / "run/foundation").exists())
            self.assertFalse((self.root / "run/workload").exists())

    def test_runbook_shows_environment_dependency_before_handoff(self):
        book = {**self.recipe, "id": "12-capstone", "alias": "12", "title": "Capstone",
                "kind": "runbook", "runDirectory": None, "modes": {}, "prerequisites": [self.recipe["id"]]}
        self.write_catalog([book, self.recipe])
        code, output = self.run_cli("start", "12")
        self.assertEqual(code, 0, output)
        self.assertIn("start 05", output)
        self.assertIn("not verified live readiness", output)
        self.assertFalse((self.root / "run").exists())

    def test_status_counts_managed_instances_only_and_never_prints_attributes(self):
        dest = self.prepare()
        (dest / "terraform.tfstate").write_text(json.dumps({"version": 4, "resources": [
            {"mode": "managed", "instances": [{"attributes": {"password": "SECRET"}}, {"attributes": {}}]},
            {"mode": "data", "instances": [{"attributes": {"access_key": "SECRET"}}]},
        ]}))
        code, output = self.run_cli("status", "--json")
        self.assertEqual(code, 0, output)
        self.assertNotIn("SECRET", output)
        result = json.loads(output)
        entry = next(item for item in result["sessions"] if item.get("labId") == "05-counter")
        self.assertEqual(entry["state"]["managedObjects"], 2)
        self.assertEqual(entry["state"]["status"], "local")
        self.assertIn("not", result["scope"].lower())

    def test_status_reports_unknown_remote_invalid_and_unregistered(self):
        dest = self.prepare()
        (dest / ".terraform").mkdir()
        (dest / ".terraform/terraform.tfstate").write_text(json.dumps({"backend": {"type": "s3", "config": {"secret_key": "SECRET"}}}))
        (dest / "terraform.tfstate").write_text(json.dumps({"version": 4, "resources": []}))
        smoke = self.root / "run/smoke-existing"
        smoke.mkdir()
        (smoke / "run.json").write_text('{"token":"SECRET"}')
        code, output = self.run_cli("status", "--json")
        data = json.loads(output)
        entry = next(item for item in data["sessions"] if item.get("labId") == "05-counter")
        self.assertEqual(entry["state"]["status"], "remote-unknown")
        self.assertIsNone(entry["state"]["managedObjects"])
        self.assertTrue(any(item["status"] == "unregistered" and item["path"] == "run/smoke-existing" for item in data["sessions"]))
        self.assertNotIn("SECRET", output)
        (dest / ".terraform/terraform.tfstate").unlink()
        (dest / "terraform.tfstate").write_text("not valid JSON")
        self.assertIn('"status": "invalid"', self.run_cli("status", "--json")[1])

    def test_status_inspects_separate_terraform_roots_and_nested_unregistered_sessions(self):
        self.recipe["runDirectory"] = "group/counter"
        self.recipe["modes"]["starter"]["files"][0]["destination"] = "bootstrap/main.tf"
        self.recipe["modes"]["starter"]["files"][1] = {"source": "labs/05-counter/starter/main.tf", "destination": "workload/main.tf"}
        self.write_catalog()
        self.assertEqual(self.run_cli("start", "05")[0], 0)
        dest = self.root / "run/group/counter"
        for name, count in (("bootstrap", 1), ("workload", 2)):
            (dest / name / "terraform.tfstate").write_text(json.dumps({"version": 4, "resources": [{"mode": "managed", "instances": [{}] * count}]}))
        (self.root / "run/group/existing").mkdir()
        code, output = self.run_cli("status", "--json")
        result = json.loads(output)
        entry = next(item for item in result["sessions"] if item.get("labId") == "05-counter")
        self.assertEqual(entry["state"]["managedObjects"], 3)
        self.assertEqual({item["path"]: item["managedObjects"] for item in entry["state"]["roots"]}, {"bootstrap": 1, "workload": 2})
        self.assertTrue(any(item["path"] == "run/group/existing" and item["status"] == "unregistered" for item in result["sessions"]))

    def test_cli_works_from_unrelated_directory_and_existing_dispatch_survives(self):
        source_root = Path(__file__).resolve().parents[2]
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("arcade", "env.sh", "lab_manager.py"):
            shutil.copy2(source_root / "scripts" / name, scripts / name)
        result = subprocess.run(["bash", str(scripts / "arcade"), "labs", "--json"], cwd="/tmp", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["recipes"][0]["alias"], "05")
        result = subprocess.run(["bash", str(scripts / "arcade"), "root"], cwd="/tmp", capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), str(self.root))

    def test_explicit_roots_exclude_child_module_from_state_count(self):
        mode = self.recipe["modes"]["starter"]
        mode["terraformRoots"] = ["."]
        mode["files"].append({"source": "labs/05-counter/starter/main.tf", "destination": "workload-module/main.tf"})
        self.write_catalog()
        dest = self.prepare()
        (dest / "terraform.tfstate").write_text(json.dumps({"version": 4, "resources": [{"mode": "managed", "instances": [{}]}]}))
        code, output = self.run_cli("status", "--json")
        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads(output)["sessions"][0]["state"]["managedObjects"], 1)

    def test_explicit_roots_must_be_unique_safe_and_have_authored_tf(self):
        for roots in ([], ["../outside"], ["missing"], [".", "."], "main.tf"):
            self.recipe["modes"]["starter"]["terraformRoots"] = roots
            self.write_catalog()
            code, output = self.run_cli("start", "05")
            self.assertEqual(code, 2, (roots, output))
            self.assertFalse((self.root / "run/counter").exists())


if __name__ == "__main__":
    unittest.main()

class EnvironmentPrerequisiteTests(unittest.TestCase):
    def test_curriculum_prerequisites_are_not_running_dependencies(self):
        recipes = manager.load_recipes(Path(__file__).resolve().parents[2])
        self.assertEqual(manager.environment_prerequisites(manager.find_recipe(recipes, '02')), [])
        self.assertEqual(manager.environment_prerequisites(manager.find_recipe(recipes, '12')), ['07-eks-foundation'])
        self.assertEqual(manager.environment_prerequisites(manager.find_recipe(recipes, '13')), ['07-eks-foundation'])

    def test_public_launch_uses_environment_dependencies(self):
        from web.launch import public_recipe
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(public_recipe(root, '02-remote-state')['environmentPrerequisites'], [])
        self.assertEqual(public_recipe(root, '12-capstone')['environmentPrerequisites'], ['07-eks-foundation'])
