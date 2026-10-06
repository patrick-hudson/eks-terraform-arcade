"""Offline practice contracts, through public operations and the real CLI."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import drill_engine


ROOT = Path(__file__).resolve().parents[2]


def authored_drill(drill_id="sample-investigation", kind="investigation"):
    return {
        "id": drill_id, "kind": kind, "title": "A request fails",
        "summary": "Choose evidence before changing anything.",
        "brief": "The client cannot reach the application.", "minutes": 8,
        "skills": ["evidence-selection"], "relatedLabs": ["08-kubernetes-release"],
        "observations": [
            {"id": "endpoints", "label": "Service endpoints", "command": "kubectl get endpointslices", "output": "ONLY REQUESTED OUTPUT"},
            {"id": "pods", "label": "Pod status", "command": "kubectl get pods", "output": "UNREVEALED OUTPUT"},
        ],
        "question": {"prompt": "Which explanation fits?", "options": [
            {"id": "selector", "text": "The selector does not match."},
            {"id": "capacity", "text": "The nodes have no capacity."},
        ]},
        "answer": {"optionId": "selector", "explanation": "PRIVATE ANSWER EXPLANATION",
                   "decisiveEvidence": ["endpoints"], "repair": "Repair the Terraform source.",
                   "verification": "Check a real request; this is simulated.",
                   "cleanup": "Destroy only the owned Terraform workspace.",
                   "followUp": "What if a second client also fails?"},
        "provenance": "Authored simulation; not a live capture.",
    }


class DrillEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arcade-drill-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "practice").mkdir()
        mission = self.root / "labs/08-kubernetes-release"
        mission.mkdir(parents=True)
        (mission / "README.md").write_text("# Mission\n")
        self.case = authored_drill()
        self.plan = authored_drill("sample-plan", "plan")
        self.write_catalogs()

    def write_catalogs(self):
        for name, record in (("cases.json", self.case), ("plan-drills.json", self.plan)):
            (self.root / "practice" / name).write_text(json.dumps({"schemaVersion": 1, "drills": [record]}))

    def test_briefs_and_list_hide_answers_and_all_observation_outputs(self):
        listing = drill_engine.list_drills(root=self.root)
        self.assertEqual(listing["schemaVersion"], 1)
        self.assertEqual([d["id"] for d in listing["drills"]], [self.case["id"], self.plan["id"]])
        for payload in (listing, drill_engine.public_drill(self.case["id"], root=self.root)):
            encoded = json.dumps(payload)
            for secret in ("ONLY REQUESTED OUTPUT", "UNREVEALED OUTPUT", "PRIVATE ANSWER EXPLANATION", '"answer"', '"optionId"'):
                self.assertNotIn(secret, encoded)
        brief = drill_engine.public_drill(self.case["id"], root=self.root)
        self.assertEqual(brief["question"], self.case["question"])
        self.assertEqual(brief["observations"][0], {k: self.case["observations"][0][k] for k in ("id", "label", "command")})

    def test_evidence_returns_only_requested_observation_and_is_a_copy(self):
        item = drill_engine.evidence(self.case["id"], "endpoints", root=self.root)
        self.assertEqual(item["drillId"], self.case["id"])
        self.assertEqual(item["output"], "ONLY REQUESTED OUTPUT")
        self.assertNotIn("UNREVEALED OUTPUT", json.dumps(item))
        self.assertNotIn("PRIVATE ANSWER EXPLANATION", json.dumps(item))
        item["output"] = "changed"
        self.assertEqual(drill_engine.evidence(self.case["id"], "endpoints", root=self.root)["output"], "ONLY REQUESTED OUTPUT")

    def test_valid_wrong_and_right_answers_return_complete_feedback_without_writes(self):
        paths = list((self.root / "practice").iterdir())
        before = {p.name: p.read_bytes() for p in paths}
        for option, correct in (("capacity", False), ("selector", True)):
            feedback = drill_engine.answer(self.case["id"], option, root=self.root)
            self.assertIs(feedback["correct"], correct)
            self.assertEqual(feedback["optionId"], option)
            self.assertEqual(feedback["correctOptionId"], "selector")
            self.assertEqual(feedback["decisiveEvidence"], ["endpoints"])
            for field in ("explanation", "repair", "verification", "cleanup", "followUp"):
                self.assertEqual(feedback[field], self.case["answer"][field])
        self.assertEqual(before, {p.name: p.read_bytes() for p in paths})

    def test_unknown_and_non_string_ids_are_rejected(self):
        for bad in ("missing", "../cases.json", "", None, [], {}):
            with self.subTest(bad=bad):
                for call in (
                    lambda: drill_engine.public_drill(bad, root=self.root),
                    lambda: drill_engine.evidence(self.case["id"], bad, root=self.root),
                    lambda: drill_engine.answer(self.case["id"], bad, root=self.root),
                ):
                    with self.assertRaises(ValueError):
                        call()

    def test_invalid_authored_contracts_are_rejected(self):
        changes = [
            lambda: self.plan.update(id=self.case["id"]),
            lambda: self.case["observations"].append(deepcopy(self.case["observations"][0])),
            lambda: self.case["question"]["options"].append(deepcopy(self.case["question"]["options"][0])),
            lambda: self.case["answer"].update(optionId="missing"),
            lambda: self.case["answer"].update(decisiveEvidence=["missing"]),
            lambda: self.case.update(relatedLabs=["../outside"]),
            lambda: self.case.update(relatedLabs=["99-missing"]),
            lambda: self.case.update(minutes=True),
            lambda: self.case.update(kind="plan"),
            lambda: self.case["answer"].pop("cleanup"),
        ]
        for change in changes:
            self.case, self.plan = authored_drill(), authored_drill("sample-plan", "plan")
            change()
            self.write_catalogs()
            with self.subTest(change=change), self.assertRaises(ValueError):
                drill_engine.list_drills(root=self.root)

    def test_invalid_envelopes_and_json_are_rejected_without_echoing_content(self):
        path = self.root / "practice/cases.json"
        for content in ("PRIVATE INVALID JSON", "[]", '{"schemaVersion":2,"drills":[]}', '{"schemaVersion":true,"drills":[]}'):
            path.write_text(content)
            with self.subTest(content=content), self.assertRaises(ValueError) as raised:
                drill_engine.list_drills(root=self.root)
            self.assertNotIn("PRIVATE INVALID JSON", str(raised.exception))

    def test_symlinked_sources_and_parent_directory_and_nonregular_files_are_rejected(self):
        path = self.root / "practice/cases.json"
        content = path.read_bytes()
        target = self.root / "source.json"
        target.write_bytes(content)
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            drill_engine.list_drills(root=self.root)
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(ValueError):
            drill_engine.list_drills(root=self.root)
        path.unlink()
        path.write_bytes(content)
        (self.root / "practice").rename(self.root / "real-practice")
        (self.root / "practice").symlink_to(self.root / "real-practice", target_is_directory=True)
        with self.assertRaises(ValueError):
            drill_engine.list_drills(root=self.root)


class AuthoredContentTests(unittest.TestCase):
    def test_seven_complete_drills_reference_real_missions_and_observations(self):
        catalog = drill_engine.list_drills()
        self.assertEqual(len(catalog["drills"]), 7)
        for card in catalog["drills"]:
            brief = drill_engine.public_drill(card["id"])
            self.assertIn("simulat", brief["provenance"].lower())
            self.assertTrue(brief["relatedLabs"])
            for lab in brief["relatedLabs"]:
                self.assertTrue((ROOT / "labs" / lab / "README.md").is_file())
            feedback = drill_engine.answer(card["id"], brief["question"]["options"][0]["id"])
            for field in ("repair", "verification", "cleanup", "followUp"):
                self.assertTrue(feedback[field].strip())
            self.assertTrue(set(feedback["decisiveEvidence"]).issubset({o["id"] for o in brief["observations"]}))

    def test_investigation_pairs_share_neutral_symptoms_but_have_distinct_evidence_and_repairs(self):
        for prefix in ("service-request", "pending-pod"):
            left, right = [drill_engine.public_drill(f"{prefix}-{variant}") for variant in ("a", "b")]
            self.assertEqual(left["brief"], right["brief"])
            self.assertEqual(left["summary"], right["summary"])
            self.assertEqual(left["skills"], right["skills"])
            self.assertEqual(left["question"], right["question"])
            feedback = [drill_engine.answer(d["id"], d["question"]["options"][0]["id"]) for d in (left, right)]
            self.assertNotEqual(feedback[0]["correctOptionId"], feedback[1]["correctOptionId"])
            self.assertNotEqual(feedback[0]["repair"], feedback[1]["repair"])
            for d, result in zip((left, right), feedback):
                self.assertGreaterEqual(len(result["decisiveEvidence"]), 2)
                self.assertIn("Terraform", result["repair"])
                self.assertIn("internet", result["verification"].lower())
                self.assertIn("simulat", result["verification"].lower())

    def test_each_investigation_answer_matches_its_decisive_observations(self):
        cases = (
            ("service-request-a", "selector", {"service": "checkout-v1", "pods": "matches zero Pods"}),
            ("service-request-b", "readiness", {"pods": "statuscode: 404", "endpoints": "ready: false", "application": "GET /readyz -> HTTP 200"}),
            ("pending-pod-a", "cpu-request", {"pod": "8000m", "nodes": "cpu=1930m", "storage": "no PersistentVolumeClaims"}),
            ("pending-pod-b", "storage-class", {"pod": "unbound immediate PersistentVolumeClaims", "storage": "arcade-gp3-fast' not found"}),
        )
        for drill_id, correct_option, facts in cases:
            with self.subTest(drill=drill_id):
                result = drill_engine.answer(drill_id, correct_option)
                self.assertTrue(result["correct"])
                for observation_id, fact in facts.items():
                    self.assertIn(observation_id, result["decisiveEvidence"])
                    self.assertIn(fact, drill_engine.evidence(drill_id, observation_id)["output"])

    def test_engine_and_cli_do_not_execute_commands_or_open_network_connections(self):
        from scripts import drill
        with patch("subprocess.Popen", side_effect=AssertionError("No command execution")), patch("socket.socket", side_effect=AssertionError("No network")):
            for arguments in (["list", "--json"], ["show", "service-request-a", "--json"],
                              ["evidence", "service-request-a", "service", "--json"],
                              ["answer", "service-request-a", "selector", "--json"]):
                with self.subTest(arguments=arguments), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(drill.main(arguments), 0)
                    self.assertIsInstance(json.loads(output.getvalue()), dict)

    def test_cli_works_outside_checkout_and_emits_stable_json_or_concise_errors(self):
        with tempfile.TemporaryDirectory(prefix="arcade-drill-cli-") as directory:
            env = {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"}
            commands = (["list"], ["show", "service-request-a"],
                        ["evidence", "service-request-a", "service"],
                        ["answer", "service-request-a", "selector"])
            for arguments in commands:
                result = subprocess.run([sys.executable, str(ROOT / "scripts/drill.py"), *arguments, "--json"], cwd=directory, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsInstance(json.loads(result.stdout), dict)
                self.assertEqual(result.stderr, "")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/drill.py"), "show", "missing", "--json"], cwd=directory, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "error")
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
