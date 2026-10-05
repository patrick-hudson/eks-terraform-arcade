import json
import re
from pathlib import Path
import tempfile
import unittest

from web.learning import LearningCatalog


ROOT = Path(__file__).resolve().parents[2]


class LearningCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = LearningCatalog(ROOT)
        self.raw = json.loads((ROOT / "web/playbooks.json").read_text())

    def test_all_twenty_four_lessons_have_complete_learning_contracts(self):
        readmes = {str(p.parent.relative_to(ROOT / "labs")) for p in (ROOT / "labs").rglob("README.md")}
        self.assertEqual(set(self.raw), readmes)
        self.assertEqual(len(self.raw), 24)
        for lesson_id, lesson in self.raw.items():
            with self.subTest(lesson=lesson_id):
                self.assertEqual(lesson["id"], lesson_id)
                self.assertEqual([s["id"] for s in lesson["stages"]], ["brief", "build", "investigate", "verify", "cleanup"])
                self.assertGreaterEqual(len(lesson["questions"]), 1)
                self.assertGreaterEqual(len(lesson["debriefPrompts"]), 2)
                self.assertTrue(set(lesson["prerequisites"]).issubset(self.raw))
                for stage in lesson["stages"]:
                    self.assertTrue(1 <= len(stage["tasks"]) <= 3)
                    self.assertTrue((ROOT / stage["sourcePath"]).is_file())
                    self.assertEqual(stage["sourcePath"], f"labs/{lesson_id}/README.md")
                    if stage["sourceHeading"]:
                        self.assertIn(stage["sourceHeading"], (ROOT / stage["sourcePath"]).read_text())
                    if stage["id"] == "investigate":
                        self.assertEqual(len(stage["hints"]), 3)

    def test_kubernetes_repairs_and_cleanup_use_terraform(self):
        for lesson_id, lesson in self.raw.items():
            if lesson_id[:2] not in {"08", "09", "10", "11", "12", "13"}:
                continue
            for stage in lesson["stages"]:
                for command in stage["commands"]:
                    with self.subTest(lesson=lesson_id, stage=stage["id"]):
                        self.assertNotRegex(command["code"], r"kubectl[^\n]*\b(?:apply|patch|delete|replace|scale|run|edit)\b")
            if "/scenario-" in lesson_id:
                cleanup = lesson["stages"][4]
                self.assertIn("terraform", json.dumps(cleanup).lower())

    def test_public_access_requires_external_http_and_preserves_narrow_access(self):
        lesson = self.raw["13-public-access"]
        verification = json.dumps(lesson["stages"][3])
        self.assertIn("curl", verification)
        self.assertIn("arcade-public-ok", verification)
        self.assertIn("/32", json.dumps(lesson))
        self.assertIn("public", lesson["questions"][0]["prompt"].lower())
        delivery = lesson["stages"][0]["tasks"][0]["success"]
        self.assertIn("NodePort", delivery)
        self.assertNotIn("without", delivery)
        self.assertIn("/32", delivery)

    def test_rollout_incident_requires_old_version_before_new_version(self):
        lesson = self.raw["11-incident-gauntlet/scenario-10"]
        baseline = lesson["stages"][1]["tasks"][0]["success"]
        repaired = lesson["stages"][3]["tasks"][0]["success"]
        self.assertIn("arcade-10-v1", baseline)
        self.assertIn("arcade-10-v2", repaired)

    def test_public_payload_never_contains_hidden_answers(self):
        for lesson_id in self.raw:
            public = self.catalog.public_lesson(lesson_id)
            encoded = json.dumps(public)
            self.assertNotIn('"hints"', encoded)
            self.assertNotIn('"correctIndex"', encoded)
            self.assertNotIn('"explanation"', encoded)
            self.assertEqual(public["stages"][2]["hintCount"], 3)
            public["stages"][0]["tasks"].clear()
            self.assertTrue(self.catalog.public_lesson(lesson_id)["stages"][0]["tasks"])

    def test_incident_briefs_do_not_name_the_injected_cause(self):
        forbidden = ("invalid tag", "wrong configmap", "exit code 23", "readiness path", "eight cpu", "get verb", "256mib", "minavailable")
        for lesson_id in self.raw:
            if "/scenario-" in lesson_id:
                lesson = self.catalog.public_lesson(lesson_id)
                brief = json.dumps({key: lesson[key] for key in ("objective", "skills")}) + json.dumps(lesson["stages"][0])
                for spoiler in forbidden:
                    self.assertNotIn(spoiler, brief.lower())

    def test_hint_returns_only_requested_level(self):
        lesson_id = "11-incident-gauntlet/scenario-01"
        hidden = self.raw[lesson_id]["stages"][2]["hints"]
        first = self.catalog.hint(lesson_id, "investigate", 1)
        self.assertEqual(first, {**hidden[0], "level": 1, "total": 3})
        self.assertNotIn(hidden[2]["body"], json.dumps(first))
        first["body"] = "changed"
        self.assertEqual(self.catalog.hint(lesson_id, "investigate", 1)["body"], hidden[0]["body"])

    def test_answers_are_evaluated_only_after_submission(self):
        for lesson_id, lesson in self.raw.items():
            for question in lesson["questions"]:
                correct = question["correctIndex"]
                self.assertEqual(self.catalog.check_answer(lesson_id, question["id"], correct), {"correct": True, "explanation": question["explanation"]})
                self.assertFalse(self.catalog.check_answer(lesson_id, question["id"], (correct + 1) % len(question["options"]))["correct"])

    def test_invalid_ids_stages_questions_and_indices_are_rejected(self):
        lesson_id = "00-terraform-contracts"
        for bad_id in ("../README.md", "", None, 1, [], {}):
            with self.assertRaises(ValueError):
                self.catalog.public_lesson(bad_id)
        for stage in ("missing", None, []):
            with self.assertRaises(ValueError):
                self.catalog.hint(lesson_id, stage, 1)
        for level in (-1, 0, 4, True, 1.0, "1", None):
            with self.assertRaises(ValueError):
                self.catalog.hint(lesson_id, "investigate", level)
        for question in ("missing", None, []):
            with self.assertRaises(ValueError):
                self.catalog.check_answer(lesson_id, question, 0)
        for index in (-1, 999, True, 1.0, "1", None):
            with self.assertRaises(ValueError):
                self.catalog.check_answer(lesson_id, "reasoning", index)

    def test_fixed_catalog_path_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "web").mkdir()
            (root / "web/playbooks.json").symlink_to(ROOT / "web/playbooks.json")
            with self.assertRaises(ValueError):
                LearningCatalog(root)


if __name__ == "__main__":
    unittest.main()
