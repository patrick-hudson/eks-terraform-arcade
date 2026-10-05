#!/usr/bin/env python3
"""Rebuild the portable kit from its authored-file inventory, never runtime state."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDED_FILES = [
    '.github/workflows/ci.yml',
    'docs/aws-testing.md',
    'docs/development.md',
    'docs/glossary.md',
    'docs/images/launcher.jpg',
    'docs/images/public-access.jpg',
    'docs/images/workspace.jpg',
    'docs/lab-launcher.md',
    'docs/learning-design.md',
    'docs/live-verification.md',
    'docs/local-rehearsal.md',
    'docs/terraform-workloads.md',
    'docs/toolchain.md',
    'docs/web-ui.md',
    'lab-recipes.json',
    'labs/06-state-rescue/fixture.py',
    'labs/10-ebs-storage/tests/test_cleanup.py',
    'labs/11-incident-gauntlet/scenario-09/ANSWERS.md',
    'labs/11-incident-gauntlet/scenario-09/HINTS.md',
    'labs/11-incident-gauntlet/scenario-09/README.md',
    'labs/11-incident-gauntlet/scenario-09/solution/fixed.yaml',
    'labs/11-incident-gauntlet/scenario-09/starter/broken.yaml',
    'labs/11-incident-gauntlet/scenario-10/ANSWERS.md',
    'labs/11-incident-gauntlet/scenario-10/HINTS.md',
    'labs/11-incident-gauntlet/scenario-10/README.md',
    'labs/11-incident-gauntlet/scenario-10/baseline/healthy.yaml',
    'labs/11-incident-gauntlet/scenario-10/solution/fixed.yaml',
    'labs/11-incident-gauntlet/scenario-10/starter/broken.yaml',
    'labs/13-public-access/ANSWERS.md',
    'labs/13-public-access/HINTS.md',
    'labs/13-public-access/README.md',
    'labs/13-public-access/preflight.sh',
    'labs/13-public-access/solution/.terraform.lock.hcl',
    'labs/13-public-access/solution/main.tf',
    'labs/13-public-access/solution/versions.tf',
    'labs/13-public-access/solution/workload.yaml',
    'labs/13-public-access/starter/.terraform.lock.hcl',
    'labs/13-public-access/starter/TASKS.md',
    'labs/13-public-access/starter/main.tf',
    'labs/13-public-access/starter/versions.tf',
    'labs/13-public-access/starter/workload.yaml',
    'labs/13-public-access/tests/test_preflight.py',
    'modules/kubernetes-exercise/.terraform.lock.hcl',
    'modules/kubernetes-exercise/main.tf',
    'modules/kubernetes-exercise/outputs.tf',
    'modules/kubernetes-exercise/root-template/.terraform.lock.hcl',
    'modules/kubernetes-exercise/root-template/main.tf',
    'modules/kubernetes-exercise/root-template/variables.tf',
    'modules/kubernetes-exercise/root-template/versions.tf',
    'modules/kubernetes-exercise/tests/assert-replacements.py',
    'modules/kubernetes-exercise/tests/contracts.tftest.hcl',
    'modules/kubernetes-exercise/tests/curriculum.tftest.hcl',
    'modules/kubernetes-exercise/tests/fixtures/extra-config.yaml',
    'modules/kubernetes-exercise/tests/fixtures/replacement-after.yaml',
    'modules/kubernetes-exercise/tests/fixtures/replacement-before.yaml',
    'modules/kubernetes-exercise/tests/fixtures/secret.yaml',
    'modules/kubernetes-exercise/tests/fixtures/shared-namespace.yaml',
    'modules/kubernetes-exercise/tests/fixtures/valid.yaml',
    'modules/kubernetes-exercise/tests/fixtures/wrong-namespace.yaml',
    'modules/kubernetes-exercise/tests/replacements.tftest.hcl',
    'modules/kubernetes-exercise/variables.tf',
    'modules/kubernetes-exercise/versions.tf',
    'scripts/arcade',
    'scripts/bootstrap-tools.sh',
    'scripts/doctor.py',
    'scripts/env.sh',
    'scripts/lab_manager.py',
    'scripts/local-check.py',
    'scripts/local_check.py',
    'scripts/package-kit.py',
    'scripts/smoke-aws.py',
    'scripts/smoke_aws.py',
    'scripts/tests/test_lab_manager.py',
    'scripts/tests/test_local_check.py',
    'scripts/tests/test_smoke_aws.py',
    'scripts/tests/test_state_rescue_fixture.py',
    'scripts/tests/test_verification.py',
    'scripts/verification.py',
    'scripts/verify-lab.py',
    'toolchain.json',
    'web/THIRD_PARTY_NOTICES.md',
    'web/app.js',
    'web/catalog.py',
    'web/core.js',
    'web/favicon.svg',
    'web/index.html',
    'web/launch.py',
    'web/launcher-core.js',
    'web/launcher.js',
    'web/learning.py',
    'web/playbooks.json',
    'web/practice-core.js',
    'web/practice.js',
    'web/server.py',
    'web/styles.css',
    'web/tests/core.test.cjs',
    'web/tests/copy-ui.test.cjs',
    'web/tests/launcher.test.cjs',
    'web/tests/practice.test.cjs',
    'web/tests/practice-ui.test.cjs',
    'web/tests/test_catalog.py',
    'web/tests/test_learning.py',
    'web/tests/test_server.py',
    'web/tests/verification.test.cjs',
    'web/vendor/DOMPurify.LICENSE',
    'web/vendor/marked.LICENSE.md',
    'web/vendor/marked.umd.js',
    'web/vendor/purify.min.js',
    'web/verification-core.js',
    'web/verification.js',
    'web/workspace.css',
]
EXCLUDED = {".git", ".terraform", "__pycache__", "node_modules", "work", "run", ".tools"}


def main():
    paths = set(ADDED_FILES)
    for line in (ROOT / "MANIFEST.sha256").read_text().splitlines():
        paths.add(line.split("  ", 1)[1])
    records = []
    for name in sorted(paths):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or EXCLUDED.intersection(path.parts):
            raise ValueError(f"Unexpected inventory path: {name}")
        if any(marker in path.name for marker in (".tfstate", ".tfplan", ".tfvars", ".pyc")):
            raise ValueError(f"Runtime file in inventory: {name}")
        source = ROOT / path
        if not source.is_file() or any(p.is_symlink() for p in [source, *source.parents] if p != ROOT.parent):
            raise ValueError(f"Source must be a regular authored file: {name}")
        records.append((hashlib.sha256(source.read_bytes()).hexdigest(), name))
    manifest = "".join(f"{digest}  {name}\n" for digest, name in records)
    (ROOT / "MANIFEST.sha256").write_text(manifest)
    archive = ROOT / "aws-interview-arcade.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in [*(name for _, name in records), "MANIFEST.sha256"]:
            bundle.write(ROOT / name, f"aws-interview-arcade/{name}")
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for digest, name in records:
            assert hashlib.sha256(bundle.read(f"aws-interview-arcade/{name}")).hexdigest() == digest
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "aws-interview-arcade.zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(json.dumps({"files": len(records) + 1, "zip_bytes": archive.stat().st_size, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
