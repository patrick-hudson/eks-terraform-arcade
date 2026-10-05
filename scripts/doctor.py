#!/usr/bin/env python3
"""Offline prerequisite checks. Never reads AWS configuration or calls AWS APIs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) > 1:
        print("Usage: arcade doctor\nChecks local executables only; no AWS authentication checks.")
        return 0 if sys.argv[1] in ("-h", "--help") else 2
    pins = {c["name"]: c["version"] for c in json.loads((ROOT / "toolchain.json").read_text())["components"]}
    checks = [
        ("terraform", ["version", "-json"], pins["Terraform"], r'"terraform_version":\s*"([^\"]+)"'),
        ("aws", ["--version"], pins["AWS CLI"], r"aws-cli/([\d.]+)"),
        ("kubectl", ["version", "--client", "-o", "json"], pins["kubectl"], r'"gitVersion":\s*"v([^\"]+)"'),
        ("kubeconform", ["-v"], pins["kubeconform"], r"v?([\d.]+)"),
        ("jq", ["--version"], pins.get("jq", "1.8.2"), r"jq-([\d.]+)"),
    ]
    failed = sys.version_info < (3, 10)
    print(f"Project: {ROOT}")
    print(f"{'FAIL' if failed else 'PASS'} Python {sys.version.split()[0]} (requires >=3.10)")
    for binary, args, expected, pattern in checks:
        executable = shutil.which(binary)
        if not executable:
            print(f"FAIL {binary}: missing; run scripts/bootstrap-tools.sh")
            failed = True
            continue
        try:
            result = subprocess.run([executable, *args], capture_output=True, text=True, timeout=20,
                                    env={**os.environ, "CHECKPOINT_DISABLE": "1"})
            match = re.search(pattern, result.stdout + result.stderr)
            actual = match.group(1) if match else "unrecognized version"
            ok = result.returncode == 0 and actual == expected
            print(f"{'PASS' if ok else 'FAIL'} {binary} {actual} (expected {expected}) — {executable}")
            failed |= not ok
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"FAIL {binary}: {type(exc).__name__}")
            failed = True
    for binary in ("bash", "curl", "unzip", "gpg", "tar", "sha256sum"):
        executable = shutil.which(binary)
        print(f"{'PASS' if executable else 'FAIL'} {binary}: {executable or 'missing'}")
        failed |= executable is None
    print("AWS authentication: not checked (offline). Lab default region: us-west-2; existing overrides are preserved.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
