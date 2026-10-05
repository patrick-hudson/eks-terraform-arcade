"""Checkout entry contracts; fixtures need no downloaded tools or AWS access."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[2]


class ArcadeEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade entry ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout with spaces"
        self.root.mkdir()
        (self.root / "scripts").mkdir()
        self.outside = Path(self.temp.name) / "unrelated directory"
        self.outside.mkdir()
        if (SOURCE / "arcade").is_file():
            shutil.copy2(SOURCE / "arcade", self.root / "arcade")
        for name in ("arcade", "env.sh"):
            shutil.copy2(SOURCE / "scripts" / name, self.root / "scripts" / name)
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(self.outside),
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def run_entry(self, *args):
        self.assertTrue((self.root / "arcade").is_file(), "The checkout needs a root arcade entry")
        self.assertTrue(os.access(self.root / "arcade", os.X_OK), "The root entry must be executable")
        return subprocess.run([str(self.root / "arcade"), *args], cwd=self.outside,
                              env=self.env, capture_output=True, text=True, timeout=10)

    def copy_script(self, name):
        shutil.copy2(SOURCE / "scripts" / name, self.root / "scripts" / name)

    def test_root_help_and_environment_work_before_path_activation(self):
        result = self.run_entry("root")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.root))
        result = self.run_entry("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("drill", "review-plan", "tui", "setup", "serve"):
            self.assertIn(command, result.stdout)
        result = self.run_entry("env")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(shlex.split(result.stdout), ["source", str(self.root / "scripts/env.sh")])

    def test_real_offline_drill_runs_with_python_and_no_lab_tools(self):
        for name in ("drill.py", "drill_engine.py"):
            self.copy_script(name)
        (self.root / "web").mkdir()
        shutil.copy2(SOURCE / "web/catalog.py", self.root / "web/catalog.py")
        shutil.copytree(SOURCE / "practice", self.root / "practice")
        for catalog in ("cases.json", "plan-drills.json"):
            for drill in json.loads((self.root / "practice" / catalog).read_text())["drills"]:
                for lab in drill["relatedLabs"]:
                    destination = self.root / "labs" / lab / "README.md"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(SOURCE / "labs" / lab / "README.md", destination)
        result = self.run_entry("drill", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        drills = json.loads(result.stdout)["drills"]
        self.assertEqual(len(drills), 7)
        result = self.run_entry("drill", "show", drills[0]["id"], "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["id"], drills[0]["id"])
        self.assertFalse((self.root / ".tools").exists())
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_review_plan_and_tui_forward_arguments_and_exit_status(self):
        for command, filename in (("review-plan", "review-plan.py"), ("tui", "arcade_tui.py")):
            (self.root / "scripts" / filename).write_text(
                "import json, os, sys\n"
                "print(json.dumps({'args':sys.argv[1:],'root':os.environ['LAB_ROOT']}))\n"
                "raise SystemExit(7)\n")
            result = self.run_entry(command, "argument with spaces", "--json")
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {"args": ["argument with spaces", "--json"], "root": str(self.root)})

    def test_setup_delegates_to_existing_installer_without_shell_profile_edits(self):
        (self.root / "scripts/bootstrap-tools.sh").write_text(
            '#!/usr/bin/env bash\nprintf "installer:%s\\n" "$@"\nexit 9\n')
        result = self.run_entry("setup", "argument with spaces")
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(result.stdout, "installer:argument with spaces\n")
        self.assertEqual(list(self.outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
