"""Run Game 06's real command blocks against fake CLIs; never contact AWS."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "labs/06-state-rescue"
BLOCKS = re.findall(r"```bash\n(.*?)```", (LAB / "README.md").read_text(), re.S)
FAKE = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
kind = pathlib.Path(sys.argv[0]).name
db = pathlib.Path(os.environ['FAKE_DB'])
state = json.loads(db.read_text())
with open(os.environ['FAKE_CALLS'], 'a') as log:
    log.write(json.dumps({'kind': kind, 'args': args, 'receipt': pathlib.Path('state-rescue-fixture.json').exists()}) + '\n')
name = '/arcade/practice-06/state-rescue'
answer = {}
if kind == 'aws':
    assert args[:8] == ['--profile', os.environ['AWS_PROFILE'], '--region', os.environ['TF_VAR_region'], '--output', 'json', '--no-cli-pager', args[7]]
    op = args[8]
    if op == 'get-caller-identity':
        answer = {'Account': os.environ.get('FAKE_ACCOUNT', '123456789012')}
    elif op == 'create-log-group':
        if state['exists']:
            print('ResourceAlreadyExistsException', file=sys.stderr)
            sys.exit(254)
        state['exists'] = True
        state['tags'] = json.loads(args[args.index('--tags') + 1])
    elif op == 'put-retention-policy':
        if os.environ.get('FAKE_RETENTION_FAIL'):
            print('AccessDeniedException', file=sys.stderr)
            sys.exit(254)
        state['retention'] = int(args[args.index('--retention-in-days') + 1])
    elif op == 'describe-log-groups':
        answer = {'logGroups': [{'logGroupName': name}] if state['exists'] else []}
    elif op == 'list-tags-log-group':
        answer = {'tags': state['tags']}
    else:
        raise AssertionError(args)
else:
    op = args[0]
    if op == 'import':
        assert args == ['import', 'aws_cloudwatch_log_group.app', name]
        state['imported'] = True
    elif op == 'show' and '-json' in args:
        resource = {'mode': 'managed', 'address': 'aws_cloudwatch_log_group.app', 'values': {
            'name': name, 'arn': 'arn:aws:logs:us-west-2:123456789012:log-group:' + name}}
        if os.environ.get('FAKE_FOREIGN_STATE'):
            resource['values']['arn'] = resource['values']['arn'].replace('123456789012', '999999999999')
        resources = [resource] if state['imported'] else []
        if os.environ.get('FAKE_EXTRA_STATE'):
            resources.append({'mode': 'managed', 'address': 'aws_s3_bucket.unrelated'})
        answer = {'values': {'root_module': {'resources': resources}}}
    elif op == 'apply':
        state['exists'] = False
        state['imported'] = False
    elif op not in {'state', 'init', 'plan', 'show'}:
        raise AssertionError(args)
db.write_text(json.dumps(state))
print(json.dumps(answer))
'''


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade fixture ")
        self.root = Path(self.temp.name)
        self.lab = self.root / "labs/06-state-rescue"
        shutil.copytree(LAB, self.lab)
        self.workspace = self.root / "run/06-state-rescue"
        self.workspace.mkdir(parents=True)
        self.receipt = self.workspace / "state-rescue-fixture.json"
        self.db = self.root / "fake.json"
        self.calls = self.root / "calls.jsonl"
        self.db.write_text(json.dumps({"exists": False, "imported": False, "tags": {}}))
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for tool in ("aws", "terraform"):
            path = bin_dir / tool
            path.write_text(f"#!{sys.executable}\n" + FAKE)
            path.chmod(0o755)
        self.env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin", "LAB_ROOT": str(self.root),
            "AWS_PROFILE": "practice", "TF_VAR_region": "us-west-2",
            "TF_VAR_expected_account_id": "123456789012", "TF_VAR_lab_id": "practice-06",
            "FAKE_DB": str(self.db), "FAKE_CALLS": str(self.calls),
            "HOME": str(self.root), "AWS_EC2_METADATA_DISABLED": "true",
        }

    def tearDown(self):
        self.temp.cleanup()

    def helper(self, *args):
        return subprocess.run([sys.executable, str(self.lab / "fixture.py"), *args],
                              cwd=self.workspace, env=self.env, capture_output=True, text=True)

    def block(self, index):
        return subprocess.run(["/bin/bash", "-c", BLOCKS[index]], cwd=self.workspace,
                              env=self.env, input="destroy\n", capture_output=True, text=True)

    def log(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_collision_cannot_claim_change_import_or_destroy_existing_group(self):
        self.db.write_text(json.dumps({"exists": True, "imported": False, "tags": {"Owner": "someone-else"}, "retention": 30}))
        self.assertNotEqual(self.block(0).returncode, 0)
        self.assertFalse(self.receipt.exists())
        for block in (3, 1, 2):  # Try the documented import, drift and teardown anyway.
            self.block(block)
        commands = [call["args"] for call in self.log()]
        for forbidden in ("put-retention-policy", "import", "apply", "delete-log-group", "plan"):
            self.assertFalse(any(forbidden in command for command in commands), forbidden)
        self.assertEqual(json.loads(self.db.read_text())["retention"], 30)
        self.assertTrue(json.loads(self.db.read_text())["exists"])

    def test_successful_fixture_import_drift_and_terraform_cleanup(self):
        created = self.block(0)
        self.assertEqual(created.returncode, 0, created.stderr)
        record = json.loads(self.receipt.read_text())
        self.assertEqual(record["profile"], "practice")
        self.assertEqual(record["log_group"], "/arcade/practice-06/state-rescue")
        retention = next(call for call in self.log() if "put-retention-policy" in call["args"])
        self.assertTrue(retention["receipt"], "Cleanup evidence must exist before retention is attempted")
        for index in (3, 1, 2):
            result = self.block(index)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(self.db.read_text())["exists"])
        self.assertTrue(self.receipt.exists())
        self.assertFalse(any("delete-log-group" in call["args"] for call in self.log()))

    def test_retention_failure_keeps_receipt_and_supports_import_then_cleanup(self):
        self.env["FAKE_RETENTION_FAIL"] = "1"
        failed = self.block(0)
        self.assertNotEqual(failed.returncode, 0)
        self.assertTrue(self.receipt.exists())
        self.assertEqual(self.helper("check").returncode, 0)
        for index in (3, 2):
            result = self.block(index)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(self.db.read_text())["exists"])

    def test_wrong_account_stops_before_create(self):
        self.env["FAKE_ACCOUNT"] = "999999999999"
        self.assertNotEqual(self.helper("create").returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(len(self.log()), 1)

    def test_missing_workspace_stops_before_helper_or_terraform(self):
        self.workspace.rmdir()
        recipes = json.loads((ROOT / "lab-recipes.json").read_text())["recipes"]
        recipe = next(item for item in recipes if item["id"] == "06-state-rescue")
        commands = [BLOCKS[index] for index in (1, 2, 3)]
        commands += [step["command"] for mode in recipe["modes"].values()
                     for step in mode["steps"] if "fixture.py\" create" in step["command"]]
        for command in commands:
            result = subprocess.run(["/bin/bash", "-c", command], cwd=self.root,
                                    env=self.env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log(), [])
        self.assertFalse((self.root / "state-rescue-fixture.json").exists())

    def test_changed_identity_or_lab_cannot_use_receipt(self):
        self.assertEqual(self.helper("create").returncode, 0)
        before = len(self.log())
        for key, replacement in (("AWS_PROFILE", "other"), ("TF_VAR_region", "us-east-1"),
                                 ("TF_VAR_expected_account_id", "999999999999"), ("TF_VAR_lab_id", "other-lab")):
            original = self.env[key]
            self.env[key] = replacement
            for args in (("name",), ("drift",), ("check", "--state")):
                self.assertNotEqual(self.helper(*args).returncode, 0, key)
            self.env[key] = original
        self.assertEqual(len(self.log()), before)

    def test_repeat_create_does_not_overwrite_receipt_or_call_aws(self):
        self.assertEqual(self.helper("create").returncode, 0)
        original = self.receipt.read_bytes()
        before = len(self.log())
        self.assertNotEqual(self.helper("create").returncode, 0)
        self.assertEqual(self.receipt.read_bytes(), original)
        self.assertEqual(len(self.log()), before)

    def test_changed_tags_prevent_import_drift_and_cleanup(self):
        self.assertEqual(self.helper("create").returncode, 0)
        state = json.loads(self.db.read_text())
        state["tags"]["LabId"] = "someone-else"
        self.db.write_text(json.dumps(state))
        before = len(self.log())
        for index in (3, 1, 2):
            self.block(index)
        for call in self.log()[before:]:
            self.assertFalse(any(op in call["args"] for op in ("put-retention-policy", "import", "plan", "apply")))

    def test_empty_foreign_or_extra_state_cannot_be_destroyed(self):
        self.assertEqual(self.helper("create").returncode, 0)
        for flag in (None, "FAKE_FOREIGN_STATE", "FAKE_EXTRA_STATE"):
            if flag:
                self.assertEqual(self.block(3).returncode, 0)
                self.env[flag] = "1"
            before = len(self.log())
            self.block(2)
            self.assertFalse(any(op in call["args"] for call in self.log()[before:] for op in ("plan", "apply")))
            if flag:
                del self.env[flag]


if __name__ == "__main__":
    unittest.main()
