"""Exercise the real shell preflight against fake read-only AWS/Kubernetes CLIs."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parents[1]
ACCOUNT = "123456789012"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/tfeks-arcade-node"
BASE = {
    "identity": {"Account": ACCOUNT},
    "cluster": {"cluster": {"name": "tfeks-arcade", "status": "ACTIVE", "endpoint": "https://example.eks.amazonaws.com", "tags": {"Project": "aws-interview-arcade", "Lab": "07", "LabId": "tfeks"}, "resourcesVpcConfig": {"clusterSecurityGroupId": "sg-0123456789abcdef0", "vpcId": "vpc-0123456789abcdef0"}}},
    "config": {"clusters": [{"cluster": {"server": "https://example.eks.amazonaws.com"}}]},
    "nodes": {"items": [{"metadata": {"name": "node-one", "labels": {"role": "lab", "eks.amazonaws.com/nodegroup": "lab"}}, "spec": {"providerID": "aws:///us-west-2a/i-0123456789abcdef0"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}]},
    "instance": {"Reservations": [{"Instances": [{"InstanceId": "i-0123456789abcdef0", "State": {"Name": "running"}, "PublicIpAddress": "198.51.100.20", "VpcId": "vpc-0123456789abcdef0", "SecurityGroups": [{"GroupId": "sg-0123456789abcdef0"}], "IamInstanceProfile": {"Arn": f"arn:aws:iam::{ACCOUNT}:instance-profile/node-profile"}, "Tags": [{"Key": k, "Value": v} for k, v in {"Project": "aws-interview-arcade", "Lab": "07", "LabId": "tfeks", "Name": "tfeks-arcade"}.items()]}]}]},
    "nodegroup": {"nodegroup": {"nodeRole": ROLE, "status": "ACTIVE"}},
    "profile": {"InstanceProfile": {"Roles": [{"Arn": ROLE}]}},
    "ip": "203.0.113.10",
}

STUB = '''#!/usr/bin/env python3
import json, os, sys
data = json.load(open(os.environ["PUBLIC_ACCESS_FIXTURE"]))
args = sys.argv[1:]
with open(os.environ["PUBLIC_ACCESS_CALLS"], "a") as out: out.write(" ".join(args) + "\\n")
choices = {"get-caller-identity":"identity", "describe-cluster":"cluster", "describe-instances":"instance", "describe-nodegroup":"nodegroup", "get-instance-profile":"profile", "config":"config", "nodes":"nodes"}
if os.path.basename(sys.argv[0]) == "curl": print(data["ip"]); sys.exit(0)
for token, key in choices.items():
    if token in args: print(json.dumps(data[key])); sys.exit(0)
print("unexpected command", file=sys.stderr); sys.exit(90)
'''


class PreflightTests(unittest.TestCase):
    def run_case(self, change=None):
        fixture = copy.deepcopy(BASE)
        if change:
            change(fixture)
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            (temp / "fixture.json").write_text(json.dumps(fixture))
            for name in ("aws", "kubectl", "curl"):
                path = temp / name
                path.write_text(STUB)
                path.chmod(0o755)
            env = dict(os.environ, PATH=f"{tmp}:{ROOT / '.tools/bin'}:{os.environ['PATH']}", AWS_PROFILE="offline-fixture", AWS_REGION="us-west-2", TF_VAR_expected_account_id=ACCOUNT, TF_VAR_lab_id="tfeks", CLUSTER_NAME="tfeks-arcade", LAB_KUBE_CONTEXT="fixture", PUBLIC_ACCESS_FIXTURE=str(temp / "fixture.json"), PUBLIC_ACCESS_CALLS=str(temp / "calls"))
            result = subprocess.run(["bash", str(LAB / "preflight.sh")], capture_output=True, text=True, env=env)
            return result

    def test_valid_identity_yields_exact_node_and_source(self):
        result = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["node_instance_id"], "i-0123456789abcdef0")
        self.assertEqual(data["allowed_cidr"], "203.0.113.10/32")
        self.assertEqual(data["public_ip"], "198.51.100.20")

    def test_wrong_account_rejected(self):
        result = self.run_case(lambda d: d["identity"].update(Account="999999999999"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("account", result.stderr.lower())

    def test_other_cluster_context_rejected(self):
        result = self.run_case(lambda d: d["config"]["clusters"][0]["cluster"].update(server="https://another.eks.amazonaws.com"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("context", result.stderr.lower())

    def test_non_arcade_cluster_rejected(self):
        result = self.run_case(lambda d: d["cluster"]["cluster"]["tags"].update(Project="production"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Game 07", result.stderr)

    def test_node_without_cluster_sg_rejected(self):
        result = self.run_case(lambda d: d["instance"]["Reservations"][0]["Instances"][0].update(SecurityGroups=[{"GroupId": "sg-other"}]))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("node", result.stderr.lower())

    def test_node_without_public_ip_rejected(self):
        result = self.run_case(lambda d: d["instance"]["Reservations"][0]["Instances"][0].pop("PublicIpAddress"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("public IPv4", result.stderr)

    def test_wrong_instance_role_rejected(self):
        result = self.run_case(lambda d: d["profile"]["InstanceProfile"]["Roles"][0].update(Arn=f"arn:aws:iam::{ACCOUNT}:role/unrelated"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("role", result.stderr.lower())

    def test_multiple_nodes_require_deliberate_selection(self):
        result = self.run_case(lambda d: d["nodes"]["items"].append(copy.deepcopy(d["nodes"]["items"][0])))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("one", result.stderr.lower())

    def test_invalid_source_ip_rejected(self):
        result = self.run_case(lambda d: d.update(ip="999.0.0.1"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source IP", result.stderr)


if __name__ == "__main__":
    unittest.main()
