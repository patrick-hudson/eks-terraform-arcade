"""Exercise the EBS cleanup process with fake CLIs; never call AWS or Kubernetes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "cleanup.sh"
FAKE = r'''
import json, os, pathlib, sys
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
with open(os.environ["TEST_LOG"], "a") as f: f.write(json.dumps([name,*args])+"\n")
if name == "terraform":
    if "output" in args:
        print("arcade-cluster" if args[-1]=="cluster_name" else "us-west-2")
    if "apply" in args and "/workload" in args[0] and os.getenv("FAIL_WORKLOAD"): sys.exit(1)
elif name == "kubectl":
    if "config" in args:
        print("https://wrong.example" if os.getenv("WRONG_CONTEXT") else "https://cluster.example")
    elif "pvc" in args: print("pvc-123")
    elif "pv" in args: print("vol-0123456789abcdef0")
elif name == "aws":
    if "get-caller-identity" in args: print("123456789012")
    elif "describe-cluster" in args: print("https://cluster.example")
    elif "wait" in args and os.getenv("FAIL_VOLUME_WAIT"): sys.exit(255)
    elif "describe-volumes" in args: print(os.getenv("REMAINING_VOLUMES", ""))
'''


class CleanupTests(unittest.TestCase):
    def run_cleanup(self, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run/10-ebs-storage/workload").mkdir(parents=True)
            (root / "run/07-eks-foundation").mkdir(parents=True)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name in ("aws", "kubectl", "terraform"):
                command = bin_dir / name
                command.write_text(f"#!{sys.executable}\n" + FAKE)
                command.chmod(0o755)
            log = root / "calls.jsonl"
            env = dict(os.environ, LAB_ROOT=str(root), LAB_KUBE_CONTEXT="arcade-lab",
                       AWS_PROFILE="test-only", TF_VAR_expected_account_id="123456789012",
                       TEST_LOG=str(log), PATH=f"{bin_dir}:{os.environ['PATH']}", **extra)
            result = subprocess.run(["bash", str(SCRIPT)], env=env, input="destroy\ndestroy\n",
                                    text=True, capture_output=True, timeout=15)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, calls

    def test_workload_destroy_then_volume_absence_then_aws_destroy(self):
        result, calls = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        applies = [(i,c) for i,c in enumerate(calls) if c[0]=="terraform" and "apply" in c]
        self.assertEqual(len(applies), 2)
        self.assertTrue(applies[0][1][1].endswith("/workload"))
        volume_wait = next(i for i,c in enumerate(calls) if c[0]=="aws" and "volume-deleted" in c)
        self.assertLess(applies[0][0], volume_wait)
        self.assertLess(volume_wait, applies[1][0])
        for c in calls:
            if c[0]=="kubectl":
                self.assertFalse(set(c) & {"delete", "apply", "patch", "edit", "run"}, c)

    def test_workload_failure_keeps_controller(self):
        result, calls = self.run_cleanup(FAIL_WORKLOAD="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0]=="terraform" and "apply" in c and not c[1].endswith("/workload") for c in calls))
        self.assertFalse(any("volume-deleted" in c for c in calls))

    def test_volume_wait_failure_keeps_controller(self):
        result, calls = self.run_cleanup(FAIL_VOLUME_WAIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0]=="terraform" and "apply" in c and not c[1].endswith("/workload") for c in calls))

    def test_remaining_volume_keeps_controller(self):
        result, calls = self.run_cleanup(REMAINING_VOLUMES="vol-11111111111111111")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tagged lab 10 volumes still exist", result.stderr)
        self.assertFalse(any(c[0]=="terraform" and "apply" in c and not c[1].endswith("/workload") for c in calls))

    def test_wrong_kubernetes_context_stops_before_mutation(self):
        result, calls = self.run_cleanup(WRONG_CONTEXT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0]=="terraform" and "apply" in c for c in calls))


if __name__ == "__main__":
    unittest.main()
