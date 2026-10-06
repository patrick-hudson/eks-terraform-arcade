"""Bounded Game 05 smoke run. Offline-tested; live validation is pending.

Preparation is local. Planning contacts AWS. Execution requires approval of the
saved plan digest and always attempts cleanup; it cannot guarantee cleanup after
power loss, SIGKILL, revoked credentials, or service/permission failures.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import uuid

SOURCE_FILES = ("main.tf", "versions.tf", "handler.py", ".terraform.lock.hcl")
OVERRIDE = 'resource "aws_iam_role_policy" "lambda" {\n  name = "${var.lab_id}-05-policy"\n}\n'
RESOURCES = {
    "aws_dynamodb_table.counter", "aws_cloudwatch_log_group.counter",
    "aws_iam_role.lambda", "aws_iam_role_policy.lambda", "aws_lambda_function.counter",
}


class SmokeError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def followup_command(root, command, path, *flags):
    return shlex.join(["python3", str(root / "scripts/smoke-aws.py"), command, "--run-dir", str(path), *flags])


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def validate_identity(profile, account_id, region):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", profile):
        raise SmokeError("Use an explicit named AWS profile (letters, digits, dots, hyphens, underscores).")
    if not re.fullmatch(r"[0-9]{12}", account_id):
        raise SmokeError("Expected account ID must contain exactly 12 digits.")
    if region not in {"us-east-1", "us-west-2"}:
        raise SmokeError("This bounded smoke recipe supports us-west-2 and us-east-1 only; review regional costs/support before extending it.")


def prepare(root, profile, account_id, region):
    validate_identity(profile, account_id, region)
    root = root.resolve()
    parent = root / "run"
    if parent.is_symlink():
        raise SmokeError("run/ must not be a symlink.")
    parent.mkdir(exist_ok=True, mode=0o700)
    path = parent / ("smoke-" + uuid.uuid4().hex[:8])
    path.mkdir(mode=0o700)
    source = root / "labs/05-serverless-counter/solution"
    hashes = {}
    for name in SOURCE_FILES:
        if (source / name).is_symlink():
            raise SmokeError("Source files must not be symlinks.")
        (path / name).write_bytes((source / name).read_bytes())
        hashes[name] = digest(path / name)
    # Pin the otherwise generated policy name so even a partial-apply teardown
    # can bind its name and parent role to this exact smoke run.
    (path / "smoke_override.tf").write_text(OVERRIDE)
    hashes["smoke_override.tf"] = digest(path / "smoke_override.tf")
    write_json(path / "smoke.auto.tfvars.json", {
        "region": region, "expected_account_id": account_id,
        "lab_id": path.name, "table_environment_key": "COUNTER_TABLE",
    })
    write_json(path / "run.json", {
        "schema_version": 1, "lab_id": path.name, "profile": profile,
        "account_id": account_id, "region": region, "created_at": now(),
        "source_hashes": hashes, "status": "prepared", "checks": {},
        "recovery_command": followup_command(root, "cleanup", path, "--execute"),
    })
    return path


def validate_plan(plan, lab_id, mode):
    """Deny expanded scope, replacements, unexpected actions, and costly settings."""
    managed = {}
    for resource in plan.get("resource_changes", []):
        address = resource.get("address")
        if resource.get("mode") == "data" and address == "data.archive_file.code":
            continue
        if address not in RESOURCES or resource.get("mode") != "managed" or address in managed:
            raise SmokeError(f"Plan contains an unapproved resource: {address}")
        managed[address] = resource["change"]
    if mode != "destroy" and set(managed) != RESOURCES:
        raise SmokeError("Plan must contain exactly the five Game 05 managed resources.")
    for address, change in managed.items():
        expected = ["create"] if mode == "create" else ["delete"] if mode == "destroy" else ["update"] if mode == "repair" and address == "aws_lambda_function.counter" else ["no-op"]
        if change.get("actions") != expected:
            raise SmokeError(f"Unexpected {mode} action for {address}: {change.get('actions')}")
        after = change.get("before" if mode == "destroy" else "after") or {}
        name_key = "function_name" if address.startswith("aws_lambda") else "name"
        expected_name = f"{lab_id}-05-lambda" if address == "aws_iam_role.lambda" else f"{lab_id}-05-policy" if address == "aws_iam_role_policy.lambda" else f"/aws/lambda/{lab_id}-05-counter" if address.startswith("aws_cloudwatch") else f"{lab_id}-05-counter"
        if after.get(name_key) != expected_name:
            raise SmokeError(f"Unapproved resource name for {address}")
        if address == "aws_iam_role_policy.lambda" and after.get("role") != f"{lab_id}-05-lambda":
            if mode != "create" or after.get("role") is not None:
                raise SmokeError("Inline policy belongs to an unapproved IAM role.")
        if mode == "destroy":
            continue
        if address.startswith("aws_dynamodb") and after.get("billing_mode") != "PAY_PER_REQUEST":
            raise SmokeError("Only on-demand DynamoDB is allowed.")
        if address.startswith("aws_cloudwatch") and after.get("retention_in_days") != 1:
            raise SmokeError("Log retention must be one day.")
        if address.startswith("aws_lambda"):
            key = "COUNTER_TABLE" if mode == "create" else "TABLE_NAME"
            if after.get("memory_size") != 256 or after.get("timeout") != 15 or after.get("environment") != [{"variables": {key: f"{lab_id}-05-counter"}}]:
                raise SmokeError("Lambda size, timeout, or environment exceeds the reviewed recipe.")
            if mode == "repair":
                before = change.get("before") or {}
                changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
                if not changed <= {"environment", "last_modified", "version", "qualified_arn", "qualified_invoke_arn"}:
                    raise SmokeError(f"Repair changes fields beyond the environment: {sorted(changed)}")
    return [{"address": address, "actions": change["actions"]} for address, change in sorted(managed.items())]


def command_runner(args, cwd, env):
    """No shell; stop the command group before the parent begins cleanup."""
    process = subprocess.Popen(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=900)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


class SmokeRun:
    def __init__(self, root, path, runner=None):
        self.root = root.resolve()
        path = Path(path)
        if not path.is_absolute():
            path = self.root / path
        if path.is_symlink() or path.parent.is_symlink() or path.resolve().parent != self.root / "run" or not re.fullmatch(r"smoke-[a-f0-9]{8}", path.name):
            raise SmokeError("Use the exact run/smoke-<id> directory created by prepare.")
        self.path = path.resolve()
        self.runner = runner or command_runner
        self.reload()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("TF_VAR_", "TF_CLI_ARGS", "AWS_")) and k not in {"TF_DATA_DIR", "TF_WORKSPACE"}}
        # HOME/config remain available for SSO and credential_process. Ambient AWS
        # environment credentials cannot silently override the named profile.
        self.env.update(AWS_PROFILE=self.data["profile"], AWS_REGION=self.data["region"],
                        AWS_DEFAULT_REGION=self.data["region"], AWS_EC2_METADATA_DISABLED="true",
                        AWS_PAGER="", TF_IN_AUTOMATION="1", TF_INPUT="0")

    def reload(self):
        self.data = json.loads((self.path / "run.json").read_text())
        if self.data.get("schema_version") != 1 or self.data.get("lab_id") != self.path.name:
            raise SmokeError("Invalid smoke run manifest.")
        validate_identity(self.data["profile"], self.data["account_id"], self.data["region"])
        self.data["recovery_command"] = followup_command(self.root, "cleanup", self.path, "--execute")

    def save(self, **values):
        self.data.update(values, updated_at=now())
        write_json(self.path / "run.json", self.data)

    @contextmanager
    def locked(self):
        with open(self.path / ".smoke.lock", "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SmokeError("Another process owns this smoke run.") from exc
            self.reload()
            yield

    def invoke_command(self, args, allow_error=False):
        if self.runner is command_runner:
            print("> " + shlex.join(args), flush=True)
        result = self.runner(args, self.path, self.env)
        if result.returncode and not allow_error:
            raise SmokeError(f"{' '.join(args[:3])} failed ({result.returncode}): {result.stderr.strip()[-3000:]}")
        return result

    def tf(self, *args):
        return self.invoke_command(["terraform", *args])

    def aws(self, *args, allow_error=False):
        return self.invoke_command(["aws", "--profile", self.data["profile"], "--region", self.data["region"], "--no-cli-pager", "--output", "json", *args], allow_error)

    def check_sources(self):
        for name, expected in self.data["source_hashes"].items():
            if name not in (*SOURCE_FILES, "smoke_override.tf") or (self.path / name).is_symlink() or digest(self.path / name) != expected:
                raise SmokeError(f"Source changed after preparation: {name}. Prepare a fresh run.")
        if set(self.data["source_hashes"]) != {*SOURCE_FILES, "smoke_override.tf"}:
            raise SmokeError("Incomplete source manifest.")
        expected = {"region": self.data["region"], "expected_account_id": self.data["account_id"], "lab_id": self.data["lab_id"], "table_environment_key": "COUNTER_TABLE"}
        if json.loads((self.path / "smoke.auto.tfvars.json").read_text()) != expected:
            raise SmokeError("Smoke input variables changed after preparation.")
        actual_tf = {p.name for p in self.path.glob("*.tf")} | {p.name for p in self.path.glob("*.tf.json")}
        extra_inputs = {p.name for p in self.path.glob("*.tfvars*")} - {"smoke.auto.tfvars.json"}
        if actual_tf != {"main.tf", "versions.tf", "smoke_override.tf"} or extra_inputs:
            raise SmokeError("Additional Terraform configuration or variable files are not allowed.")

    def preflight(self):
        self.check_sources()
        identity = json.loads(self.aws("sts", "get-caller-identity").stdout)
        if identity.get("Account") != self.data["account_id"]:
            raise SmokeError("AWS profile resolves to a different account; no Terraform action was started.")
        self.save(identity={"Account": identity["Account"], "Arn": identity.get("Arn")})

    def make_plan(self, mode):
        name = {"create": "initial", "repair": "repair", "verify": "verify", "destroy": "destroy"}[mode]
        args = ["plan", "-input=false", "-no-color", "-lock-timeout=30s", f"-out={name}.tfplan"]
        if mode == "destroy":
            args.append("-destroy")
        if mode in {"repair", "verify"}:
            args.append("-var=table_environment_key=TABLE_NAME")
        self.tf(*args)
        plan = json.loads(self.tf("show", "-json", f"{name}.tfplan").stdout)
        summary = validate_plan(plan, self.data["lab_id"], mode)
        write_json(self.path / f"{name}-plan.json", plan)
        write_json(self.path / f"{name}-review.json", {"resources": summary, "plan_sha256": digest(self.path / f"{name}.tfplan")})
        return name

    def plan(self):
        with self.locked():
            if self.data["status"] not in {"prepared", "planned"}:
                raise SmokeError("This run has already started. Use cleanup or prepare a fresh run.")
            self.preflight()
            self.tf("init", "-input=false", "-no-color", "-lockfile=readonly")
            self.tf("validate", "-no-color")
            self.make_plan("create")
            approval = digest(self.path / "initial.tfplan")
            self.save(status="planned", plan_sha256=approval, planned_at=now())
            return approval

    def invoke(self, counter, name):
        result = json.loads(self.aws("lambda", "invoke", "--function-name", f"{self.path.name}-05-counter", "--cli-binary-format", "raw-in-base64-out", "--payload", json.dumps({"counter": counter}), f"{name}.json").stdout)
        payload = json.loads((self.path / f"{name}.json").read_text())
        return result, payload

    def stored_item(self, counter):
        result = self.aws("dynamodb", "get-item", "--table-name", f"{self.path.name}-05-counter", "--key", json.dumps({"pk": {"S": counter}}), "--consistent-read")
        # The CLI can return empty stdout when the requested item does not exist.
        return json.loads(result.stdout.strip() or "{}")

    def stored_visits(self):
        return int(self.stored_item("smoke")["Item"]["visits"]["N"])

    def exercise(self):
        function = f"{self.path.name}-05-counter"
        self.aws("lambda", "wait", "function-active-v2", "--function-name", function)
        transport, payload = self.invoke("smoke", "broken-response")
        if transport.get("StatusCode") != 200 or not transport.get("FunctionError") or payload.get("errorType") != "KeyError" or "TABLE_NAME" not in payload.get("errorMessage", ""):
            raise SmokeError("Deployment did not reproduce the expected TABLE_NAME KeyError; inspect broken-response.json.")
        self.data["checks"]["expected_fault"] = "KeyError: TABLE_NAME"
        self.save()
        self.make_plan("repair")
        self.tf("apply", "-input=false", "-no-color", "repair.tfplan")
        self.aws("lambda", "wait", "function-updated-v2", "--function-name", function)
        visits = []
        for index in (1, 2):
            transport, payload = self.invoke("smoke", f"fixed-response-{index}")
            if transport.get("FunctionError") or transport.get("StatusCode") != 200 or payload.get("statusCode") != 200 or payload.get("counter") != "smoke" or type(payload.get("visits")) is not int:
                raise SmokeError("Repaired Lambda did not return the expected successful counter response.")
            visits.append(payload["visits"])
        if visits != [1, 2] or self.stored_visits() != 2:
            raise SmokeError("Fresh counter did not return 1 then 2 with a stored value of 2.")
        transport, payload = self.invoke("NOT-VALID", "invalid-response")
        if transport.get("FunctionError") or transport.get("StatusCode") != 200 or payload.get("statusCode") != 400 or self.stored_visits() != 2 or self.stored_item("NOT-VALID").get("Item"):
            raise SmokeError("Invalid input was not rejected without changing the stored counter or creating an invalid item.")
        self.data["checks"].update(increments=visits, invalid_input_did_not_write=True)
        self.make_plan("verify")
        self.data["checks"]["converged"] = True
        self.save()

    def verify_absence(self):
        lab = self.path.name
        checks = [
            ("lambda", ["lambda", "get-function", "--function-name", f"{lab}-05-counter"], "ResourceNotFoundException"),
            ("dynamodb", ["dynamodb", "describe-table", "--table-name", f"{lab}-05-counter"], "ResourceNotFoundException"),
            ("iam_role", ["iam", "get-role", "--role-name", f"{lab}-05-lambda"], "NoSuchEntity"),
        ]
        absence, failures = [], []
        for name, args, code in checks:
            result = self.aws(*args, allow_error=True)
            if result.returncode and f"({code})" in result.stderr:
                absence.append(name)
            else:
                failures.append(f"{name}: {result.stderr.strip() or 'resource still present'}")
        result = self.aws("logs", "describe-log-groups", "--log-group-name-prefix", f"/aws/lambda/{lab}-05-counter", allow_error=True)
        if result.returncode:
            failures.append("log_group: " + result.stderr.strip())
        elif any(x["logGroupName"] == f"/aws/lambda/{lab}-05-counter" for x in json.loads(result.stdout).get("logGroups", [])):
            failures.append("log_group: resource still present")
        else:
            absence.append("log_group")
        self.data["checks"]["absence"] = absence
        self.save()
        if failures:
            raise SmokeError("AWS absence not proven: " + "; ".join(failures))

    def destroy(self):
        self.save(cleanup_started_at=now())
        self.make_plan("destroy")
        self.tf("apply", "-input=false", "-no-color", "destroy.tfplan")
        if self.tf("state", "list").stdout.strip():
            raise SmokeError("Terraform state is not empty after destroy.")
        self.aws("dynamodb", "wait", "table-not-exists", "--table-name", f"{self.path.name}-05-counter")
        self.verify_absence()
        self.save(cleanup_finished_at=now())

    def execute(self, approval):
        with self.locked():
            if self.data["status"] != "planned" or approval != self.data.get("plan_sha256") or approval != digest(self.path / "initial.tfplan"):
                raise SmokeError("Execution requires the exact saved plan SHA256 and an unused planned run.")
            self.preflight()
            # Reinspect the binary being approved, rather than trusting an editable summary.
            validate_plan(json.loads(self.tf("show", "-json", "initial.tfplan").stdout), self.path.name, "create")
            self.save(status="running", execution_started_at=now())
            passed = False
            try:
                self.tf("apply", "-input=false", "-no-color", "initial.tfplan")
                self.exercise()
                passed = True
            except BaseException as error:
                self.save(error=f"{type(error).__name__}: {error}")
                raise
            finally:
                try:
                    self.destroy()
                    self.save(status="passed-cleaned" if passed else "failed-cleaned")
                except BaseException as error:
                    self.save(status="cleanup-failed", cleanup_error=f"{type(error).__name__}: {error}")
                    raise SmokeError(f"Cleanup failed; resources may remain. {error}\nRecovery: {self.data['recovery_command']}") from error

    def cleanup(self):
        with self.locked():
            if self.data["status"] in {"prepared", "planned"}:
                raise SmokeError("This run has never applied resources; no cleanup action is needed.")
            self.preflight()
            try:
                self.tf("init", "-input=false", "-no-color", "-lockfile=readonly")
                self.destroy()
                self.save(status="recovered-cleaned", cleanup_error=None)
            except BaseException as error:
                self.save(status="cleanup-failed", cleanup_error=f"{type(error).__name__}: {error}")
                raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare", help="Create a local working copy; no AWS calls.")
    prepare_parser.add_argument("--profile", required=True)
    prepare_parser.add_argument("--account-id", required=True)
    prepare_parser.add_argument("--region", required=True, choices=["us-west-2", "us-east-1"])
    for name in ("run", "cleanup"):
        child = sub.add_parser(name)
        child.add_argument("--run-dir", required=True)
        child.add_argument("--execute", action="store_true")
        if name == "run":
            child.add_argument("--approve-plan")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "prepare":
            path = prepare(root, args.profile, args.account_id, args.region)
            print(f"Prepared locally: {path}\nNo AWS calls made. Next: {followup_command(root, 'run', path)}")
            return 0
        run = SmokeRun(root, Path(args.run_dir))
        if args.command == "cleanup":
            if not args.execute:
                raise SmokeError("Cleanup changes AWS resources; rerun with --execute for this run only.")
            run.cleanup()
        elif args.execute:
            if not args.approve_plan:
                raise SmokeError("Review initial-plan.json and initial-review.json, then supply --approve-plan SHA256.")
            run.execute(args.approve_plan)
        else:
            if args.approve_plan:
                raise SmokeError("--approve-plan is only valid with --execute.")
            approval = run.plan()
            print(f"AWS read-only plan prepared; nothing applied.\nReview: {run.path / 'initial-review.json'}\nFull plan: {run.path / 'initial-plan.json'}\nPlan SHA256: {approval}\nAfter review: {followup_command(root, 'run', run.path, '--execute', '--approve-plan', approval)}")
            return 0
        print(f"Result: {run.data['status']}\nEvidence: {run.path / 'run.json'}\nTerraform state and reports retained locally.")
        return 0
    except (SmokeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Smoke run stopped: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Check run.json for cleanup status and recovery command.", file=sys.stderr)
        return 130


def cli():
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    return main()
