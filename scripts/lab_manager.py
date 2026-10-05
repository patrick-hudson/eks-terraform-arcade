#!/usr/bin/env python3
"""Prepare authored practice files locally. Recipe commands are never executed."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ".arcade-session.json"
DENIED_PARTS = {".git", ".aws", ".terraform", "__pycache__", ".tools", ".env", RECEIPT}
SUFFIXES = {".tf", ".hcl", ".py", ".yaml", ".yml", ".json", ".md", ".sh"}


class LauncherError(ValueError):
    pass


def relative_path(value: str, *, authored: bool = False) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or any(ord(c) < 32 for c in value):
        raise LauncherError("Recipe paths must be nonempty relative paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise LauncherError(f"Unsafe recipe path: {value}")
    if any(part in DENIED_PARTS for part in path.parts) or any(".tfstate" in part or part.endswith((".tfplan", ".tfvars", ".tfvars.json")) for part in path.parts):
        raise LauncherError(f"State, credentials and runtime files cannot be copied: {value}")
    if authored and (path.parts[0] not in {"labs", "modules"} or path.suffix not in SUFFIXES):
        raise LauncherError(f"Source must be an authored file under labs/ or modules/: {value}")
    return path


def contained_path(root: Path, relative: str | PurePosixPath) -> Path:
    """Reject symlinks even when they happen to point back inside the project."""
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise LauncherError(f"Refusing symlink path: {path.relative_to(root)}")
    return path


def read_json(path: Path, *, limit: int = 2_000_000):
    if path.is_symlink():
        raise LauncherError(f"Refusing symlink file: {path.name}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise LauncherError(f"Expected a regular file: {path.name}")
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise LauncherError(f"Expected a regular file: {path.name}")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise LauncherError(f"File is too large to inspect safely: {path.name}")
    return json.loads(raw)


def load_recipes(root: Path) -> list[dict]:
    catalog = read_json(contained_path(root, "lab-recipes.json"))
    if not isinstance(catalog, dict) or catalog.get("schemaVersion") != 1 or not isinstance(catalog.get("recipes"), list):
        raise LauncherError("lab-recipes.json must contain schemaVersion 1 and a recipes array.")
    recipes, identifiers, destinations = catalog["recipes"], set(), set()
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise LauncherError("Every recipe must be an object.")
        for key in ("id", "alias", "title", "cost"):
            if not isinstance(recipe.get(key), str) or not recipe[key].strip():
                raise LauncherError(f"Recipe is missing {key}.")
        for key in ("id", "alias"):
            if not re.fullmatch(r"[a-z0-9][a-z0-9/-]*", recipe[key]) or recipe[key] in identifiers:
                raise LauncherError(f"Invalid or duplicate recipe identifier: {recipe[key]}")
            identifiers.add(recipe[key])
        if recipe.get("kind") not in {"terraform", "kubernetes", "runbook"}:
            raise LauncherError(f"Unknown recipe kind: {recipe['id']}")
        modes = recipe.get("modes")
        if not isinstance(modes, dict) or set(modes) - {"starter", "guided"}:
            raise LauncherError(f"Unknown preparation mode: {recipe['id']}")
        if not isinstance(recipe.get("prerequisites"), list) or not all(isinstance(x, str) for x in recipe["prerequisites"]):
            raise LauncherError(f"Invalid prerequisite list: {recipe['id']}")
        if recipe["kind"] == "runbook":
            if modes or recipe.get("runDirectory") is not None:
                raise LauncherError("Runbook recipes cannot create workspaces.")
            continue
        run_path = relative_path(recipe.get("runDirectory"))
        if any(run_path == old or run_path in old.parents or old in run_path.parents for old in destinations):
            raise LauncherError(f"Overlapping run directories: {run_path}")
        destinations.add(run_path)
        if not modes:
            raise LauncherError(f"Recipe has no preparation modes: {recipe['id']}")
        for mode in modes.values():
            if not isinstance(mode, dict) or not all(isinstance(mode.get(k), str) and mode[k] for k in ("label", "description")):
                raise LauncherError(f"Invalid preparation mode: {recipe['id']}")
            if not isinstance(mode.get("files"), list) or not mode["files"]:
                raise LauncherError(f"Mode has no explicit file list: {recipe['id']}")
            files = set()
            for item in mode["files"]:
                if not isinstance(item, dict):
                    raise LauncherError("Recipe file entries must be objects.")
                relative_path(item.get("source"), authored=True)
                destination = relative_path(item.get("destination"))
                if any(destination == old or destination in old.parents or old in destination.parents for old in files):
                    raise LauncherError(f"Overlapping destination files: {destination}")
                files.add(destination)
            if "terraformRoots" in mode:
                roots = mode["terraformRoots"]
                if not isinstance(roots, list) or not roots or not all(isinstance(path, str) for path in roots) or len(set(roots)) != len(roots):
                    raise LauncherError(f"Invalid Terraform root list: {recipe['id']}")
                tf_directories = {str(path.parent) for path in files if path.suffix == ".tf"}
                for path in roots:
                    if path != ".":
                        relative_path(path)
                    if path not in tf_directories:
                        raise LauncherError(f"Terraform root has no authored configuration: {path}")
            for key in ("steps", "cleanup"):
                if not isinstance(mode.get(key), list) or not all(isinstance(step, dict) and all(isinstance(step.get(k), str) and step[k] for k in ("title", "command")) for step in mode[key]):
                    raise LauncherError(f"Invalid {key} commands: {recipe['id']}")
    canonical_ids = {recipe["id"] for recipe in recipes}
    for recipe in recipes:
        if not set(recipe["prerequisites"]) <= canonical_ids:
            raise LauncherError(f"Unknown prerequisite: {recipe['id']}")
    return recipes


def find_recipe(recipes: list[dict], identifier: str) -> dict:
    for recipe in recipes:
        if identifier in {recipe["id"], recipe["alias"]}:
            return recipe
    raise LauncherError(f"Unknown lab {identifier!r}. Run arcade labs for IDs.")


def session_receipt(directory: Path, recipe: dict) -> dict:
    receipt_path = directory / RECEIPT
    if not receipt_path.exists() and not receipt_path.is_symlink():
        raise LauncherError(f"Existing directory is unregistered; nothing was changed: {directory}. Inspect it manually; arcade will not adopt state or overwrite files.")
    receipt = read_json(receipt_path)
    if (not isinstance(receipt, dict) or receipt.get("schemaVersion") != 1
            or receipt.get("labId") != recipe["id"] or receipt.get("mode") not in recipe["modes"]
            or not isinstance(receipt.get("preparedAt"), str) or not isinstance(receipt.get("sourceHashes"), dict)
            or not receipt["sourceHashes"]):
        raise LauncherError(f"Invalid or mismatched session receipt in {directory}; nothing was changed.")
    for path, digest in receipt["sourceHashes"].items():
        relative_path(path)
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise LauncherError(f"Invalid source hash in {directory}; nothing was changed.")
    return receipt


def copy_source(source: Path, destination: Path) -> str:
    # O_NOFOLLOW prevents the final source file from being swapped for a symlink.
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        source_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(source_stat.st_mode):
            raise LauncherError(f"Recipe source is not a regular file: {source.name}")
        data = stream.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(data)
    destination.chmod(stat.S_IMODE(source_stat.st_mode) & 0o777)
    return hashlib.sha256(data).hexdigest()


def publish_directory(staging: Path, destination: Path) -> None:
    """Linux atomic no-replace rename, unlike os.rename which replaces empty dirs."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise LauncherError("Atomic workspace preparation requires Linux/WSL2 renameat2 support.")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def prepare(root: Path, recipe: dict, requested_mode: str | None) -> tuple[Path, str, bool]:
    directory = contained_path(root, "run/" + recipe["runDirectory"])
    if directory.exists():
        if not directory.is_dir():
            raise LauncherError(f"Workspace path is not a directory: {directory}")
        receipt = session_receipt(directory, recipe)
        if requested_mode is not None and requested_mode != receipt["mode"]:
            raise LauncherError(f"This session uses {receipt['mode']} mode. Mode changes are refused to preserve your edits and state. Resume with arcade start {recipe['alias']}.")
        return directory, receipt["mode"], False
    mode = requested_mode or ("starter" if "starter" in recipe["modes"] else next(iter(recipe["modes"])))
    if mode not in recipe["modes"]:
        raise LauncherError(f"Lab {recipe['alias']} has no {mode} mode; choose {', '.join(recipe['modes'])}.")
    sources = []
    for item in recipe["modes"][mode]["files"]:
        source = contained_path(root, relative_path(item["source"], authored=True))
        if not source.is_file():
            raise LauncherError(f"Missing authored recipe file: {item['source']}")
        sources.append((source, item["destination"]))
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".arcade-prepare-", dir=directory.parent))
    try:
        hashes = {target: copy_source(source, staging / target) for source, target in sources}
        receipt = {"schemaVersion": 1, "labId": recipe["id"], "mode": mode,
                   "preparedAt": datetime.now(timezone.utc).isoformat(), "sourceHashes": hashes}
        (staging / RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        publish_directory(staging, directory)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return directory, mode, True


def print_prerequisites(root: Path, recipe: dict, recipes: list[dict]) -> None:
    """Show dependency order without preparing or checking any environment."""
    ordered, seen = [], {recipe["id"]}

    def visit(identifier: str) -> None:
        if identifier in seen:
            return
        seen.add(identifier)
        prerequisite = find_recipe(recipes, identifier)
        for dependency in prerequisite["prerequisites"]:
            visit(dependency)
        ordered.append(prerequisite)

    for identifier in recipe["prerequisites"]:
        visit(identifier)
    if not ordered:
        print("\nPrerequisite Terraform environments: none declared.")
        return
    print("\nPrerequisite Terraform setup order (complete before this exercise):")
    entry = shlex.quote(str(root / "arcade"))
    for number, prerequisite in enumerate(ordered, 1):
        print(f"{number}. {prerequisite['alias']} — {prerequisite['title']}")
        print(f"   {entry} start {prerequisite['alias']}")
    print("Prepared files are not verified live readiness. Follow each prerequisite runbook's verification before continuing.")


def print_steps(root: Path, recipe: dict, mode: str, directory: Path) -> None:
    chosen = recipe["modes"][mode]
    print(f"\n{recipe['title']} — {chosen['label']}\n{chosen['description']}\nCost: {recipe['cost']}")
    print("\nRun these commands yourself. Preparation executes no Terraform, kubectl or AWS commands.")
    print(f"\nsource {shlex.quote(str(root / 'scripts/env.sh'))}\ncd {shlex.quote(str(directory))}")
    for key, label in (("steps", "Next steps"), ("cleanup", "Cleanup after practice")):
        print(f"\n{label}:")
        for number, step in enumerate(chosen[key], 1):
            print(f"\n# {number}. {step['title']}\n{step['command']}")
    print(f"\nFull runbook: {root / 'labs' / recipe['id'] / 'README.md'}")
    print(f"Resume: arcade next {recipe['alias']}")


def state_summary(directory: Path) -> dict:
    def unknown(status: str, note: str) -> dict:
        return {"status": status, "managedObjects": None, "note": note}

    try:
        if os.environ.get("TF_DATA_DIR"):
            return unknown("data-directory-unknown", "TF_DATA_DIR is set; backend metadata outside the default directory was not inspected.")
        metadata = contained_path(directory, ".terraform/terraform.tfstate")
        if metadata.exists():
            backend = read_json(metadata, limit=10_000_000).get("backend")
            if not isinstance(backend, dict) or backend.get("type") not in {None, "local"}:
                return unknown("remote-unknown", "Remote backend; no remote state or AWS queries were made.")
            config = backend.get("config") or {}
            if not isinstance(config, dict) or config.get("path") not in {None, "terraform.tfstate"}:
                return unknown("local-path-unknown", "Custom local backend path; inspect with Terraform in this workspace.")
        workspace = contained_path(directory, ".terraform/environment")
        if os.environ.get("TF_WORKSPACE", "default") != "default" or (workspace.exists() and workspace.read_text().strip() != "default"):
            return unknown("workspace-unknown", "A nondefault Terraform workspace may be selected; inspect it with Terraform.")
        path = contained_path(directory, "terraform.tfstate")
        if not path.exists():
            return unknown("no-local-state", "No default local state snapshot. This does not establish cloud absence.")
        snapshot = read_json(path, limit=50_000_000)
        if not isinstance(snapshot, dict) or snapshot.get("version") != 4 or not isinstance(snapshot.get("resources"), list):
            return unknown("invalid", "Unrecognized local state format; inspect it with Terraform.")
        count = 0
        for resource in snapshot["resources"]:
            if (not isinstance(resource, dict) or resource.get("mode") not in {"managed", "data"}
                    or not isinstance(resource.get("instances"), list)
                    or not all(isinstance(instance, dict) for instance in resource["instances"])):
                return unknown("invalid", "Unrecognized local state resource structure.")
            if resource["mode"] == "managed":
                count += len(resource["instances"])
        return {"status": "local", "managedObjects": count, "note": "Managed objects in the default local state snapshot only; AWS was not queried."}
    except (OSError, ValueError, AttributeError):
        return unknown("invalid", "State could not be safely read; no cloud absence conclusion is possible.")


def workspace_state(directory: Path, recipe: dict, mode: str) -> dict:
    chosen = recipe["modes"][mode]
    roots = chosen.get("terraformRoots")
    if roots is None:
        roots = sorted({str(PurePosixPath(item["destination"]).parent) for item in chosen["files"]
                        if item["destination"].endswith((".tf", ".tf.json"))})
    if not roots or roots == ["."]:
        return state_summary(directory)
    summaries = [{"path": path, **state_summary(contained_path(directory, path))} for path in roots]
    total = sum(item["managedObjects"] for item in summaries) if all(item["managedObjects"] is not None for item in summaries) else None
    return {"status": "multiple-roots", "managedObjects": total, "roots": summaries,
            "note": "Only Terraform directories named by this recipe were inspected; any unknown root prevents a combined count."}


def collect_status(root: Path, recipes: list[dict]) -> dict:
    sessions, registered_paths = [], set()
    for recipe in recipes:
        if recipe["runDirectory"] is None:
            continue
        relative = "run/" + recipe["runDirectory"]
        base = {"labId": recipe["id"], "alias": recipe["alias"], "path": relative}
        registered_paths.add(relative)
        try:
            directory = contained_path(root, relative)
            if not directory.exists():
                sessions.append({**base, "status": "not-prepared"})
                continue
            receipt = session_receipt(directory, recipe)
            sessions.append({**base, "status": "prepared", "mode": receipt["mode"], "preparedAt": receipt["preparedAt"],
                             "state": workspace_state(directory, recipe, receipt["mode"]) if recipe["kind"] == "terraform" else {"status": "not-inspected", "managedObjects": None, "note": "Kubernetes objects were not queried."}})
        except (OSError, ValueError):
            sessions.append({**base, "status": "unregistered", "note": "Existing path has no valid matching session receipt; inspect manually."})
    def unregistered_children(parent: Path):
        for child in sorted(parent.iterdir()):
            relative = child.relative_to(root).as_posix()
            if relative in registered_paths:
                continue
            if not child.is_symlink() and child.is_dir() and any(path.startswith(relative + "/") for path in registered_paths):
                unregistered_children(child)
            elif child.is_dir() or child.is_symlink():
                sessions.append({"path": relative, "status": "unregistered", "note": "Existing run directory was not created by this launcher; inspect manually (including smoke runs)."})
    run = contained_path(root, "run")
    if run.is_dir():
        unregistered_children(run)
    return {"schemaVersion": 1, "scope": "Local files only. AWS and Kubernetes were not queried; an empty state or missing directory does not prove cleanup.", "sessions": sessions}


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("labs", "status"):
        command = commands.add_parser(name)
        command.add_argument("--json", action="store_true", help="Print machine-readable local data")
    for name in ("start", "next"):
        command = commands.add_parser(name)
        command.add_argument("id", help="Lab alias, such as 05 or 11-01, or canonical ID")
        if name == "start":
            command.add_argument("--mode", choices=("starter", "guided"), help="New sessions default to starter where available; existing sessions preserve their mode")
    args = parser.parse_args(argv)
    try:
        root = root.resolve()
        recipes = load_recipes(root)
        if args.command == "labs":
            public = [{**{k: r[k] for k in ("id", "alias", "title", "kind", "runDirectory", "prerequisites", "cost")},
                       "modes": {name: {k: mode[k] for k in ("label", "description")} for name, mode in r["modes"].items()}} for r in recipes]
            if args.json:
                print(json.dumps({"schemaVersion": 1, "recipes": public}, indent=2))
            else:
                print("Local lab launcher — prepares files; never applies cloud resources.\n")
                for recipe in public:
                    print(f"{recipe['alias']:6} {recipe['title']} [{', '.join(recipe['modes']) or 'runbook'}]\n       {recipe['cost']}")
                print("\nChoose: arcade start ID [--mode starter|guided]\nResume instructions: arcade next ID\nInspect local sessions: arcade status")
        elif args.command == "status":
            result = collect_status(root, recipes)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result["scope"] + "\n")
                for session in result["sessions"]:
                    state = session.get("state", {})
                    details = f"; state={state['status']}" if state else ""
                    if state.get("managedObjects") is not None:
                        details += f"; managed objects={state['managedObjects']}"
                    print(f"{session.get('alias', '—'):6} {session['status']}{details} — {session['path']}")
                    for item in state.get("roots", []):
                        count = f"; managed objects={item['managedObjects']}" if item["managedObjects"] is not None else ""
                        print(f"       {item['path']}: {item['status']}{count}")
        else:
            recipe = find_recipe(recipes, args.id)
            if recipe["kind"] == "runbook":
                print_prerequisites(root, recipe, recipes)
                print(f"{recipe['title']} is a runbook; no standalone workspace is prepared.\nRead: {root / 'labs' / recipe['id'] / 'README.md'}")
                return 0
            if args.command == "start":
                directory, mode, created = prepare(root, recipe, args.mode)
                print(f"{'Prepared' if created else 'Resuming'} {directory}\n{'Only explicitly listed practice files were copied.' if created else 'All edits and state were preserved; no files were copied.'}")
            else:
                directory = contained_path(root, "run/" + recipe["runDirectory"])
                if not directory.exists():
                    raise LauncherError(f"Lab is not prepared. Run arcade start {recipe['alias']} first.")
                mode = session_receipt(directory, recipe)["mode"]
            print_prerequisites(root, recipe, recipes)
            print_steps(root, recipe, mode, directory)
        return 0
    except (OSError, ValueError) as error:
        # Avoid JSON parser excerpts that could accidentally print state contents.
        message = "A local JSON file is invalid; inspect the recipe or session file." if isinstance(error, json.JSONDecodeError) else str(error)
        print(f"arcade: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
