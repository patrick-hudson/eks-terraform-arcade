"""Synthetic fixtures exercise the local reader; real Terraform has a separate proof."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plan_review

ROOT = Path(__file__).resolve().parents[2]
CANARY = "SECRET_CANARY_DO_NOT_PRINT"


def resource(name, actions, **extra):
    return {"address": "terraform_data." + name, "mode": "managed",
            "change": {"actions": actions}, **extra}


def plan(resources=(), **extra):
    return {"format_version": "1.2", "planned_values": {},
            "applyable": True, "complete": True, "errored": False,
            "resource_changes": list(resources), **extra}


class PlanReviewTests(unittest.TestCase):
    def invoke(self, data, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/review-plan.py"), "-", *args],
            input=json.dumps(data) if not isinstance(data, str) else data,
            capture_output=True, text=True, timeout=10,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )

    def test_actions_count_operations_separately_from_objects_and_addresses(self):
        actions = [["create"], ["read"], ["update"], ["delete"], ["no-op"],
                   ["delete", "create"], ["create", "delete"]]
        result = plan_review.review_plan(plan([
            resource("r" + str(i), action) for i, action in enumerate(actions)
        ]))
        changes = result["changes"]
        self.assertEqual(changes["resourceCount"], 7)
        self.assertEqual(changes["changeCount"], 7)
        self.assertEqual(changes["actionCounts"],
                         {"create": 3, "read": 1, "update": 1, "delete": 3, "no-op": 1})
        self.assertEqual(changes["replacementCount"], 2)
        self.assertEqual(changes["resources"][5]["replacementOrder"], "delete-before-create")
        self.assertEqual(changes["resources"][6]["replacementOrder"], "create-before-delete")
        self.assertEqual(len({row["explanation"] for row in changes["resources"]}), 7)
        self.assertIn("downtime", changes["resources"][6]["explanation"])
        self.assertIn("ownership", " ".join(result["limitations"]).lower())
        self.assertIn("price", " ".join(result["limitations"]).lower())

    def test_move_import_drift_unknown_and_deferred_are_separate(self):
        moved = resource("new", ["no-op"], previous_address="terraform_data.old")
        imported = resource("imported", ["no-op"])
        imported["change"].update(importing={"id": CANARY}, after_unknown={"id": True})
        result = plan_review.review_plan(plan(
            [moved, imported], complete=False, applyable=False,
            resource_drift=[resource("drifted", ["update"])],
            deferred_changes=[{"reason": "resource_config_unknown",
                               "resource_change": resource("later", ["create"])}],
        ))
        self.assertEqual(result["changes"]["moveCount"], 1)
        self.assertEqual(result["changes"]["importCount"], 1)
        self.assertEqual(result["changes"]["unknownValueCount"], 1)
        self.assertEqual(result["changes"]["actionCounts"]["update"], 0)
        self.assertEqual(result["changes"]["actionCounts"]["create"], 0)
        self.assertEqual(result["drift"]["actionCounts"]["update"], 1)
        self.assertEqual(result["deferred"]["changeCount"], 1)
        self.assertIs(result["metadata"]["complete"], False)
        self.assertTrue(any("incomplete" in s for s in result["uncertainties"]))
        self.assertNotIn(CANARY, json.dumps(result))

    def test_secret_values_keys_import_ids_and_control_characters_never_escape(self):
        entry = resource("item", ["delete", "create"])
        entry["address"] = 'module.group["' + CANARY + '\\"suffix"].terraform_data.item["' + CANARY + '"]'
        entry["previous_address"] = 'terraform_data.old["' + CANARY + '\\n"]'
        entry.update(name=CANARY, type=CANARY, provider_name=CANARY,
                     action_reason=CANARY, deposed=CANARY)
        entry["change"].update(
            before={CANARY: CANARY}, after={"value": CANARY},
            before_sensitive={CANARY: True}, after_sensitive={CANARY: True},
            after_unknown={CANARY: True}, importing={"id": CANARY},
            replace_paths=[[CANARY]],
        )
        data = plan([entry], variables={CANARY: {"value": CANARY}},
                    output_changes={CANARY: {"actions": ["update"], "after": CANARY,
                                              "after_unknown": True}},
                    planned_values={"outputs": {CANARY: {"value": CANARY}}},
                    prior_state={"values": {"secret": CANARY}},
                    configuration={"secret": CANARY}, terraform_version=CANARY,
                    future_field=CANARY)
        for flags in [[], ["--json"]]:
            with self.subTest(flags=flags):
                result = self.invoke(data, *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
                self.assertIn("redacted", result.stdout)
        entry["address"] = "terraform_data.\x1b[31mitem\n"
        summary = plan_review.review_plan(plan([entry]))
        self.assertNotIn("\x1b", plan_review.format_review(summary))
        self.assertNotIn("\n", summary["changes"]["resources"][0]["address"])

    def test_unknown_actions_do_not_become_no_op_or_echo_untrusted_tokens(self):
        for actions in [["forget"], [CANARY], ["update", "create"], ["create", "forget"]]:
            with self.subTest(actions=actions):
                result = plan_review.review_plan(plan([resource("x", actions)]))
                self.assertEqual(result["changes"]["unsupportedCount"], 1)
                self.assertEqual(result["changes"]["actionCounts"]["no-op"], 0)
                self.assertEqual(sum(result["changes"]["actionCounts"].values()), 0)
                self.assertIn("unsupported", result["changes"]["resources"][0]["explanation"])
                self.assertNotIn(CANARY, json.dumps(result))

    def test_missing_and_invalid_metadata_do_not_mean_success(self):
        data = plan()
        for key in ("complete", "applyable", "errored"):
            del data[key]
        result = plan_review.review_plan(data)
        self.assertEqual(result["metadata"], {"complete": None, "applyable": None, "errored": None})
        self.assertEqual(len(result["uncertainties"]), 3)
        data["complete"] = CANARY
        with self.assertRaises(plan_review.PlanReviewError) as caught:
            plan_review.review_plan(data)
        self.assertNotIn(CANARY, str(caught.exception))

    def test_malformed_documents_fail_without_echoing_input(self):
        invalid = [CANARY, [], {"format_version": "1.2", "values": {}},
                   {"type": "planned_change", "@message": CANARY},
                   plan(format_version="2.0"), plan(format_version=CANARY),
                   plan(resource_changes={CANARY: 1}), plan([None]),
                   plan([{"address": CANARY}]), plan([resource("x", [])]),
                   plan([resource("x", [1])]), plan(deferred_changes=[{}])]
        for data in invalid:
            with self.subTest(data=data):
                result = self.invoke(data, "--json")
                self.assertEqual(result.returncode, 2)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_single_document_json_and_input_caps(self):
        for raw in [b"{}\n{}", b"\xff", b"[" * 2000, b'{"format_version": NaN}']:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(plan_review.PlanReviewError):
                    plan_review.read_plan(io.BytesIO(raw))
        with self.assertRaises(plan_review.PlanReviewError):
            plan_review.read_plan(io.BytesIO(b" " * (plan_review.MAX_INPUT_BYTES + 1)))
        with self.assertRaises(plan_review.PlanReviewError):
            plan_review.review_plan(plan([resource("x", ["no-op"])] * 10001))
        with self.assertRaises(plan_review.PlanReviewError):
            plan_review.review_plan(plan([resource("x", ["no-op"])] * 5001,
                                         resource_drift=[resource("x", ["update"])] * 5000))

    def test_truncated_details_preserve_all_counts_and_uncertainties(self):
        resources = [resource("r" + str(i), ["create"]) for i in range(160)]
        resources[-1]["change"]["after_unknown"] = {"value": True}
        result = plan_review.review_plan(plan(resources))["changes"]
        self.assertEqual(result["resourceCount"], 160)
        self.assertEqual(result["actionCounts"]["create"], 160)
        self.assertEqual(result["unknownValueCount"], 1)
        self.assertLess(len(result["resources"]), 160)
        self.assertEqual(result["omittedCount"], 160 - len(result["resources"]))

    def test_deposed_objects_count_as_two_changes_on_one_address(self):
        result = plan_review.review_plan(plan([
            resource("x", ["no-op"]), resource("x", ["delete"], deposed="abcd1234")
        ]))["changes"]
        self.assertEqual(result["resourceCount"], 1)
        self.assertEqual(result["changeCount"], 2)
        self.assertTrue(result["resources"][1]["deposed"])

    def test_file_and_stdin_match_and_do_not_write_input(self):
        data = plan([resource("x", ["update"])])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT / "scripts/review-plan.py"),
                                     str(path), "--json"], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), json.loads(self.invoke(data, "--json").stdout))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["plan.json"])


if __name__ == "__main__":
    unittest.main()
