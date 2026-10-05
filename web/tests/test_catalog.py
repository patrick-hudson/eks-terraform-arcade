"""Contract and source-boundary tests; no AWS access or third-party packages."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from web.catalog import Catalog, FileNotAllowed


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def write_fixture(root, files):
    lines = []
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        lines.append(f"{hashlib.sha256(content.encode()).hexdigest()}  {name}")
    (root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def test_real_catalog_has_fourteen_labs_and_ten_neutral_incidents(self):
        payload = Catalog(PROJECT_ROOT).build()
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual([lab["number"] for lab in payload["labs"]], [f"{n:02}" for n in range(14)])
        incidents = payload["labs"][11]["scenarios"]
        self.assertEqual([s["title"] for s in incidents], [f"Incident {n:02}" for n in range(1, 11)])
        self.assertEqual(incidents[0]["id"], "11-incident-gauntlet/scenario-01")
        self.assertIn("release never starts", incidents[0]["summary"])

    def test_public_access_is_a_kubernetes_lab_and_glossary_is_discoverable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root, {
                "labs/13-public-access/README.md": "# 13 - Public access\n\nProve real internet HTTP.\n",
                "docs/glossary.md": "# Plain-English field guide\n\nA Service routes traffic.\n",
                "modules/kubernetes-exercise/root-template/main.tf": 'module "exercise" {}\n',
                "modules/kubernetes-exercise/run/private.tf": "runtime",
                "modules/kubernetes-exercise/terraform.tfvars": "secret",
            })
            catalog = Catalog(root)
            payload = catalog.build()
            self.assertEqual(payload["labs"][0]["track"], "Kubernetes")
            self.assertEqual(payload["docs"][0]["id"], "glossary")
            self.assertIn('module "exercise"', catalog.read_file("modules/kubernetes-exercise/root-template/main.tf")["content"])
            for path in ("modules/kubernetes-exercise/run/private.tf", "modules/kubernetes-exercise/terraform.tfvars"):
                with self.assertRaises(FileNotAllowed):
                    catalog.read_file(path)

    def test_every_listed_source_is_exact_authored_content(self):
        catalog = Catalog(PROJECT_ROOT)
        payload = catalog.build()
        entries = payload["labs"] + [s for lab in payload["labs"] for s in lab["scenarios"]]
        paths = {doc["path"] for doc in payload["docs"]}
        for entry in entries:
            paths.update(entry[key] for key in ("readme", "hints", "answers") if entry[key])
            paths.update(file["path"] for file in entry["files"])
        for path in paths:
            with self.subTest(path=path):
                result = catalog.read_file(path)
                self.assertEqual(result["path"], path)
                self.assertEqual(result["content"], (PROJECT_ROOT / path).read_bytes().decode("utf-8"))

    def test_reference_and_refactor_files_are_solutions(self):
        payload = Catalog(PROJECT_ROOT).build()
        for lab in payload["labs"]:
            for file in lab["files"]:
                if "/solution/" in file["path"] or "/refactor/" in file["path"]:
                    self.assertEqual(file["kind"], "solution")
        self.assertFalse(any("/scenario-" in file["path"] for file in payload["labs"][11]["files"]))

    def test_allowlist_excludes_runtime_hidden_state_secrets_and_nonmanifest_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root, {
                "README.md": "# Kit\n",
                "labs/00-example/README.md": "# 00 - Example\n\nPractice the task.\n",
                "labs/00-example/solution/main.tf": "resource \"terraform_data\" \"x\" {}\r\n",
                "labs/00-example/solution/.terraform.lock.hcl": "hidden",
                "labs/00-example/solution/production.tfvars": "secret",
                "labs/00-example/run/output.py": "runtime",
                "labs/00-example/state/snapshot.hcl": "state",
                "labs/00-example/solution/terraform.tfstate": "state",
                "labs/00-example/solution/preview.tfplan": "plan",
                "run/secret.md": "runtime",
                ".credentials.md": "hidden",
            })
            (root / "labs/00-example/solution/secret.py").write_text("unlisted")
            catalog = Catalog(root)
            self.assertEqual(catalog.read_file("labs/00-example/solution/main.tf")["content"], 'resource "terraform_data" "x" {}\r\n')
            for path in (
                "labs/00-example/solution/.terraform.lock.hcl", "labs/00-example/solution/production.tfvars",
                "labs/00-example/run/output.py", "labs/00-example/state/snapshot.hcl",
                "labs/00-example/solution/terraform.tfstate", "labs/00-example/solution/preview.tfplan",
                "run/secret.md", ".credentials.md", "labs/00-example/solution/secret.py",
                "../README.md", "/README.md", "labs/../README.md", "labs\\00-example\\README.md",
            ):
                with self.subTest(path=path), self.assertRaises(FileNotAllowed):
                    catalog.read_file(path)

    def test_symlinks_are_denied_even_after_catalog_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = "labs/00-example/solution/main.tf"
            write_fixture(root, {target: "original", "docs/setup.md": "safe"})
            catalog = Catalog(root)
            (root / target).unlink()
            (root / target).symlink_to(root / "docs/setup.md")
            with self.assertRaises(FileNotAllowed):
                catalog.read_file(target)
            (root / target).unlink()
            (root / "labs/00-example/solution").rmdir()
            (root / "labs/00-example/solution").symlink_to(root / "docs", target_is_directory=True)
            with self.assertRaises(FileNotAllowed):
                catalog.read_file(target)

    def test_catalog_never_reads_answer_or_hint_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root, {
                "README.md": "# Kit\n",
                "labs/11-incident-gauntlet/README.md": "# Game 11 - Gauntlet\n\nDebug releases.\n",
                "labs/11-incident-gauntlet/scenario-01/README.md": "# Scenario 01\n\nA release is unavailable.\n",
                "labs/11-incident-gauntlet/scenario-01/HINTS.md": "# LEAK_HINT\nFault: classified hint",
                "labs/11-incident-gauntlet/scenario-01/ANSWERS.md": "# LEAK_ANSWER\nFault: classified answer",
            })
            serialized = json.dumps(Catalog(root).build())
            self.assertNotIn("LEAK_", serialized)
            self.assertNotIn("classified", serialized)
            self.assertIn("Incident 01", serialized)

    def test_new_web_guide_is_an_explicit_exception_to_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root, {"README.md": "# Kit\n"})
            (root / "docs").mkdir()
            (root / "docs/web-ui.md").write_text("# Local guide\n")
            catalog = Catalog(root)
            self.assertIn("docs/web-ui.md", [doc["path"] for doc in catalog.build()["docs"]])
            self.assertEqual(catalog.read_file("docs/web-ui.md")["content"], "# Local guide\n")


if __name__ == "__main__":
    unittest.main()
