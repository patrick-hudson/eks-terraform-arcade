"""Local rehearsals for authored Game00 and Game05 contracts, without live state."""
import argparse
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 1024 * 1024
OUTPUT_LIMIT = 64 * 1024
PROCESS_TIMEOUT = 60
LABS = {
    "00": {
        "id": "00-terraform-contracts", "directory": "00-contracts",
        "files": ("main.tf", "variables.tf"),
        "coverage": "Eight Terraform plan checks: stable service names, memory values, and invalid input.",
        "limits": "This checks Game00's local Terraform contract. It does not create resources or prove any AWS behavior.",
    },
    "05": {
        "id": "05-serverless-counter", "directory": "05-serverless-counter",
        "files": ("handler.py",),
        "coverage": "Three Python checks: invalid counter names, missing settings, and decoding a DynamoDB response.",
        "limits": "This checks the Python handler with a fake AWS client. It does not check Terraform, live IAM permissions, Lambda settings, or concurrent DynamoDB writes.",
    },
}
EXECUTION_NOTE = "Runs your code locally in a temporary folder. This is not a security sandbox; only check code you trust."


class SetupError(Exception):
    """A missing prerequisite or unsupported input prevents the check."""


def default_workspace(root, lab):
    return root / "run" / LABS[lab]["directory"]


def checked_path(path):
    """Do not follow symlinks, including a symlink in a parent directory."""
    path = Path(os.path.abspath(os.path.expanduser(str(path))))
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise SetupError(f"Use a real directory and files, not a symbolic link: {candidate}")
    return path


def read_file(path):
    path = checked_path(path)
    try:
        # NONBLOCK also prevents a file-to-FIFO race from hanging the reader.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise SetupError(f"Expected a regular file: {path}")
            if info.st_size > MAX_FILE_BYTES:
                raise SetupError(f"File is too large for this rehearsal (limit 1 MiB): {path}")
            data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise SetupError(f"File is too large for this rehearsal (limit 1 MiB): {path}")
            return data
    except FileNotFoundError as exc:
        raise SetupError(f"Missing {path.name}. Write this file in your lab workspace first: {path.parent}") from exc
    except OSError as exc:
        raise SetupError(f"Could not read {path}: {exc.strerror}") from exc


def isolated_environment(temp):
    home = temp / "home"
    home.mkdir()
    (home / "aws-config").write_text("")
    (home / "aws-credentials").write_text("")
    return {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(home), "TMPDIR": str(temp), "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "AWS_CONFIG_FILE": str(home / "aws-config"),
        "AWS_SHARED_CREDENTIALS_FILE": str(home / "aws-credentials"),
        "AWS_EC2_METADATA_DISABLED": "true", "AWS_PAGER": "",
        "TF_IN_AUTOMATION": "1", "TF_INPUT": "0", "CHECKPOINT_DISABLE": "1",
    }


def run_bounded(command, cwd, env, *, timeout=PROCESS_TIMEOUT, output_limit=OUTPUT_LIMIT):
    """Stop the process group on a deadline or excessive output; retain bounded text."""
    start = time.monotonic()
    output = bytearray()
    reason = None
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = timeout - (time.monotonic() - start)
                    if remaining <= 0:
                        reason = "timeout"
                        break
                    for key, _ in selector.select(min(remaining, 0.1)):
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        available = output_limit - len(output)
                        output.extend(data[:available])
                        if len(data) > available:
                            reason = "output-limit"
                            break
                    if reason:
                        break
                if not reason:
                    try:
                        process.wait(timeout=max(0.001, timeout - (time.monotonic() - start)))
                    except subprocess.TimeoutExpired:
                        reason = "timeout"
        finally:
            # Also end children that inherited the process group or stdout pipe.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    return {
        "exitCode": process.returncode,
        "stopReason": reason,
        "durationSeconds": round(time.monotonic() - start, 3),
        "output": output.decode("utf-8", errors="replace"),
    }


def commands_for(lab, root, temp, env):
    if lab == "05":
        (temp / "test_handler.py").write_bytes(read_file(root / "labs/05-serverless-counter/solution/test_handler.py"))
        (temp / "boto3.py").write_text(
            "def client(*args, **kwargs):\n"
            "    raise RuntimeError('Local rehearsal: an AWS client was requested outside the fake test client.')\n"
            "def resource(*args, **kwargs):\n"
            "    raise RuntimeError('Local rehearsal does not create AWS resources.')\n"
        )
        # -I ignores PYTHONPATH and user site packages. Only our temporary files
        # are then added for the trusted test module and the learner's handler.
        runner = (
            "import os,sys,unittest; sys.path.insert(0,os.getcwd()); "
            "import boto3; "
            "suite=unittest.defaultTestLoader.loadTestsFromName('test_handler'); "
            "result=unittest.TextTestRunner(verbosity=2).run(suite); "
            "sys.exit(0 if result.wasSuccessful() else 1)"
        )
        return [("Python handler", [sys.executable, "-I", "-B", "-c", runner])]

    terraform = shutil.which("terraform", path=env["PATH"])
    if not terraform:
        raise SetupError('Terraform was not found. Run arcade setup, then source "$(arcade root)/scripts/env.sh".')
    contracts = read_file(root / "labs/00-terraform-contracts/solution/tests/contracts.tftest.hcl")
    text = contracts.decode("utf-8")
    commands = re.findall(r"^\s*command\s*=\s*(\w+)", text, re.MULTILINE)
    runs = re.findall(r'^\s*run\s+"', text, re.MULTILINE)
    if len(commands) != len(runs) or not runs or set(commands) != {"plan"}:
        raise SetupError("The repository's Game00 tests must all explicitly use command = plan.")
    (temp / "tests").mkdir()
    (temp / "tests/contracts.tftest.hcl").write_bytes(contracts)
    (temp / "provider-mirror").mkdir()
    config = temp / "terraform.rc"
    config.write_text('disable_checkpoint = true\nprovider_installation {\n'
                      '  filesystem_mirror { path = "' + str(temp / "provider-mirror") + '" }\n}\n')
    env["TF_CLI_CONFIG_FILE"] = str(config)
    env["TF_DATA_DIR"] = str(temp / "terraform-data")
    return [
        ("Prepare temporary Terraform folder", [terraform, "init", "-backend=false", "-get=false", "-input=false", "-no-color"]),
        ("Terraform service contracts", [terraform, "test", "-no-color", "-filter=tests/contracts.tftest.hcl"]),
    ]


def rehearse(lab, workspace, *, root=ROOT):
    spec = LABS[lab]
    workspace = checked_path(workspace)
    if not workspace.is_dir():
        raise SetupError(f"Lab workspace was not found: {workspace}. Run arcade start {lab} first, or use --workspace PATH.")
    report = {
        "schemaVersion": 1, "labId": spec["id"], "workspace": str(workspace),
        "status": "passed", "coverage": spec["coverage"], "limits": spec["limits"],
        "executionNote": EXECUTION_NOTE, "checks": [],
    }
    with tempfile.TemporaryDirectory(prefix="arcade-check-") as directory:
        temp = Path(directory)
        for filename in spec["files"]:
            (temp / filename).write_bytes(read_file(workspace / filename))
        env = isolated_environment(temp)
        for title, command in commands_for(lab, root, temp, env):
            result = run_bounded(command, temp, env)
            result["title"] = title
            report["checks"].append(result)
            if result["exitCode"] or result["stopReason"]:
                report["status"] = "failed"
                break
    return report


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description="Rehearse Games 00 and 05 locally using trusted tests. No cloud apply. " + EXECUTION_NOTE)
    parser.add_argument("lab", choices=tuple(LABS) + tuple(spec["id"] for spec in LABS.values()))
    parser.add_argument("--workspace", type=Path, help="Folder containing your main.tf and variables.tf (00), or handler.py (05)")
    parser.add_argument("--json", action="store_true", help="Print one JSON report")
    args = parser.parse_args(argv)
    lab = args.lab[:2]
    try:
        report = rehearse(lab, args.workspace or default_workspace(root, lab), root=root)
        exit_code = 0 if report["status"] == "passed" else 1
    except (SetupError, OSError, UnicodeError) as exc:
        report = {"schemaVersion": 1, "labId": LABS[lab]["id"], "status": "setup-error", "message": str(exc)}
        exit_code = 2
    if args.json:
        print(json.dumps(report, indent=2))
    elif exit_code == 2:
        print("Could not start the local check: " + report["message"], file=sys.stderr)
    else:
        print(f"Game {lab}: local checks {report['status']}")
        print(report["coverage"])
        for check in report["checks"]:
            print(f"\n{check['title']}\n{check['output'].rstrip()}")
            if check["stopReason"]:
                print("Stopped: " + {"timeout": "the check took longer than 60 seconds.", "output-limit": "the check printed more than 64 KiB."}[check["stopReason"]])
        print("\n" + report["limits"])
        print(report["executionNote"])
    return exit_code
