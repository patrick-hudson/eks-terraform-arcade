"""Read a Terraform show plan locally, constructing a value-free summary.

Only explicitly selected metadata enters the result. Never render, log or copy
arbitrary input objects: values can also occur in keys, selectors and import IDs.
This module neither invokes Terraform nor writes the input to disk.
"""
import argparse
import json
import re
import sys
import unicodedata

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_RESOURCES = 10_000
DETAIL_LIMIT = 100
ACTION_NAMES = ("create", "read", "update", "delete", "no-op")
EXPLANATIONS = {
    ("create",): "Create a new object.",
    ("read",): "Read a data source; this does not create a managed object.",
    ("update",): "Update the existing object in place.",
    ("delete",): "Delete the existing object.",
    ("no-op",): "No resource value change is proposed; move or import markers can still be present.",
    ("delete", "create"): "Replace by deleting the old object before creating its replacement; consider the interruption.",
    ("create", "delete"): "Replace by creating the replacement before deleting the old object; this does not prove zero downtime or sufficient capacity.",
}
LIMITATIONS = [
    "This is a local interpretation of supplied Terraform plan JSON, not live cloud evidence or approval to apply.",
    "Resource ownership, live behavior and price have not been verified.",
    "Values, variables, outputs, import IDs and string address selectors are omitted; inspect sensitive details privately in your existing review workflow.",
]


class PlanReviewError(ValueError):
    """An input cannot be interpreted; messages must not include input content."""


def _invalid_json_constant(_value):
    raise PlanReviewError("Expected standard JSON; non-finite numbers are not supported.")


def read_plan(stream):
    """Read one JSON document from a binary or text stream without retaining it."""
    try:
        data = stream.read(MAX_INPUT_BYTES + 1)
        if isinstance(data, str):
            data = data.encode("utf-8")
        if len(data) > MAX_INPUT_BYTES:
            raise PlanReviewError("Plan input exceeds the 10 MiB limit.")
        document = json.loads(data.decode("utf-8"), parse_constant=_invalid_json_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, PlanReviewError):
            raise
        raise PlanReviewError("Could not read one UTF-8 JSON object. Use terraform show -json on a saved plan, not plan -json event output.") from None
    return document


def _address(value):
    """Redact selectors before rendering; even escaped quotes stay inside a key."""
    if not isinstance(value, str) or not value:
        raise PlanReviewError("A resource record is missing a valid address.")
    result = []
    index = 0
    while index < len(value):
        character = value[index]
        if character == "[":
            end = index + 1
            quoted = False
            escaped = False
            while end < len(value):
                current = value[end]
                if escaped:
                    escaped = False
                elif current == "\\" and quoted:
                    escaped = True
                elif current == '"':
                    quoted = not quoted
                elif current == "]" and not quoted:
                    break
                end += 1
            selector = value[index + 1:end]
            result.append("[" + selector + "]" if re.fullmatch(r"[0-9]+", selector)
                          else '["<redacted>"]')
            index = min(end + 1, len(value))
        else:
            # C includes terminal controls, surrogates and invisible bidi controls.
            result.append("?" if unicodedata.category(character).startswith("C") else character)
            index += 1
    return "".join(result)


def _mask_status(mask):
    """Return (has unknown values, invalid mask) without copying mask keys."""
    pending = [mask]
    unknown = False
    invalid = False
    while pending:
        item = pending.pop()
        if isinstance(item, bool):
            unknown |= item
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        else:
            invalid = True
    return unknown, invalid


def _records(document, key):
    records = document.get(key, [])
    if not isinstance(records, list):
        raise PlanReviewError("Resource changes, drift and deferred changes must be arrays.")
    return records


def _summarize(records):
    summary = {
        "resourceCount": 0, "changeCount": len(records),
        "actionCounts": {name: 0 for name in ACTION_NAMES},
        "replacementCount": 0, "moveCount": 0, "importCount": 0,
        "unknownValueCount": 0, "invalidUnknownMaskCount": 0,
        "unsupportedCount": 0, "resources": [], "omittedCount": max(0, len(records) - DETAIL_LIMIT),
    }
    addresses = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("change"), dict):
            raise PlanReviewError("Each resource record must have an address and a change object.")
        address = _address(record.get("address"))
        addresses.add(record["address"])
        change = record["change"]
        actions = change.get("actions")
        if not isinstance(actions, list) or not actions or not all(isinstance(item, str) for item in actions):
            raise PlanReviewError("Each change must have a nonempty array of action names.")
        sequence = tuple(actions)
        supported = sequence in EXPLANATIONS
        replacement = supported and len(sequence) == 2
        if supported:
            for action in actions:
                summary["actionCounts"][action] += 1
        else:
            summary["unsupportedCount"] += 1
        moved = "previous_address" in record
        previous = _address(record["previous_address"]) if moved else None
        importing = "importing" in change and change["importing"] is not None
        if importing and not isinstance(change["importing"], dict):
            raise PlanReviewError("An import marker must be an object.")
        unknown, invalid_mask = _mask_status(change.get("after_unknown", {}))
        summary["replacementCount"] += replacement
        summary["moveCount"] += moved
        summary["importCount"] += importing
        summary["unknownValueCount"] += unknown
        summary["invalidUnknownMaskCount"] += invalid_mask
        if len(summary["resources"]) < DETAIL_LIMIT:
            summary["resources"].append({
                "address": address,
                "actions": list(sequence) if supported else ["unsupported"],
                "explanation": EXPLANATIONS.get(sequence, "An unsupported action sequence is present; its effects are not counted as known actions."),
                "replacementOrder": ("delete-before-create" if actions[0] == "delete" else "create-before-delete") if replacement else None,
                "previousAddress": previous,
                "importing": importing,
                "deposed": "deposed" in record,
                "unknownValues": unknown,
            })
    summary["resourceCount"] = len(addresses)
    return summary


def review_plan(document):
    """Construct an allowlisted report from a version-1 Terraform plan object."""
    if not isinstance(document, dict):
        raise PlanReviewError("Expected one Terraform show JSON plan object.")
    version = document.get("format_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", version):
        raise PlanReviewError("Missing or invalid format_version. Use terraform show -json on a saved plan.")
    if version.split(".", 1)[0] != "1":
        raise PlanReviewError("Unsupported plan format major version; this reader supports version 1.x.")
    if "values" in document or not any(key in document for key in ("planned_values", "configuration", "resource_changes", "deferred_changes")):
        raise PlanReviewError("Expected a saved plan, not state or streaming event JSON. Use terraform show -json PLANFILE.")
    for key in ("planned_values", "configuration"):
        if key in document and not isinstance(document[key], dict):
            raise PlanReviewError("Plan metadata has an invalid object shape.")
    metadata = {}
    uncertainties = []
    for key in ("complete", "applyable", "errored"):
        value = document.get(key)
        if key in document and not isinstance(value, bool):
            raise PlanReviewError("Plan completeness, applicability and error flags must be booleans.")
        metadata[key] = value
        if value is None:
            uncertainties.append(f"The {key} flag is missing; its status is unknown.")
    if metadata["complete"] is False:
        uncertainties.append("Terraform marks this plan incomplete; another plan/apply round may be needed.")
    if metadata["applyable"] is False:
        uncertainties.append("Terraform marks this plan not applyable; this can also occur for a no-change plan.")
    if metadata["errored"] is True:
        uncertainties.append("Terraform reports a planning error; the listed changes are only partial evidence.")

    changes = _records(document, "resource_changes")
    drift = _records(document, "resource_drift")
    deferred = _records(document, "deferred_changes")
    if len(changes) + len(drift) + len(deferred) > MAX_RESOURCES:
        raise PlanReviewError("Plan exceeds the 10,000 resource-record limit across changes, drift and deferrals.")
    deferred_records = []
    for item in deferred:
        if not isinstance(item, dict) or not isinstance(item.get("resource_change"), dict):
            raise PlanReviewError("Each deferred entry must contain a resource_change object.")
        deferred_records.append(item["resource_change"])
    report = {
        "schemaVersion": 1,
        "evidenceKind": "local-plan-interpretation",
        "metadata": metadata,
        "changes": _summarize(changes),
        "drift": _summarize(drift),
        "deferred": _summarize(deferred_records),
        "unknownOutputCount": 0,
        "uncertainties": uncertainties,
        "limitations": list(LIMITATIONS),
    }
    outputs = document.get("output_changes", {})
    if not isinstance(outputs, dict):
        raise PlanReviewError("Output changes must be an object.")
    for output in outputs.values():
        if not isinstance(output, dict):
            raise PlanReviewError("Each output change must be an object.")
        unknown, invalid_mask = _mask_status(output.get("after_unknown", {}))
        report["unknownOutputCount"] += unknown
        if invalid_mask and "An output unknown-value mask is unrecognized." not in uncertainties:
            uncertainties.append("An output unknown-value mask is unrecognized.")
    if report["unknownOutputCount"]:
        uncertainties.append("Some output values are unknown until apply; their names and values are omitted.")
    for key, label in (("changes", "Proposed changes"), ("drift", "Observed drift"), ("deferred", "Deferred changes")):
        summary = report[key]
        if summary["unsupportedCount"]:
            uncertainties.append(f"{label} include unsupported action sequences; known action counts exclude those records.")
        if summary["unknownValueCount"]:
            uncertainties.append(f"{label} include values unknown until apply; unknown is not the same as empty or absent.")
        if summary["invalidUnknownMaskCount"]:
            uncertainties.append(f"{label} include unrecognized unknown-value masks; value completeness cannot be determined.")
    if drift:
        uncertainties.append("Observed drift compares refreshed observations with prior saved state; it is separate from the proposed actions and does not prove current cloud health.")
    if deferred:
        uncertainties.append("Deferred changes are not included in proposed action counts; their eventual actions may differ after missing information is available.")
    return report


def format_review(report):
    lines = ["Local Terraform plan review (values omitted)"]
    lines.extend(report["limitations"])
    lines.append("Metadata: " + ", ".join(
        key + "=" + ("unknown" if value is None else str(value).lower())
        for key, value in report["metadata"].items()))
    for key, label in (("changes", "Proposed changes"), ("drift", "Observed drift"), ("deferred", "Deferred changes")):
        group = report[key]
        lines.extend(["", f"{label}: {group['resourceCount']} resource addresses, {group['changeCount']} object-change records",
                      "  Action counts: " + ", ".join(f"{name}={count}" for name, count in group["actionCounts"].items()),
                      f"  Replacements={group['replacementCount']}, moves={group['moveCount']}, imports={group['importCount']}, unknown-value records={group['unknownValueCount']}, unsupported={group['unsupportedCount']}"])
        for row in group["resources"]:
            lines.append(f"  {row['address']}: {row['explanation']}")
            if row["previousAddress"] is not None:
                lines.append(f"    Move from {row['previousAddress']}; the action above still applies.")
            if row["importing"]:
                lines.append("    Import marker present; import ID omitted. Import does not establish ownership.")
            if row["deposed"]:
                lines.append("    This change describes a deposed object at the same resource address.")
            if row["unknownValues"]:
                lines.append("    Some resulting values are unknown until apply.")
        if group["omittedCount"]:
            lines.append(f"  {group['omittedCount']} detail rows omitted; counts include every record.")
    lines.extend(["", "Uncertainty:"])
    lines.extend("  " + item for item in report["uncertainties"])
    if not report["uncertainties"]:
        lines.append("  No uncertainty markers were found in the inspected metadata; the limitations above still apply.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explain local Terraform show plan JSON without displaying values or approving apply.")
    parser.add_argument("path", help="Terraform show JSON file, or - for standard input")
    parser.add_argument("--json", action="store_true", help="Print the value-free summary as JSON")
    args = parser.parse_args(argv)
    try:
        if args.path == "-":
            document = read_plan(getattr(sys.stdin, "buffer", sys.stdin))
        else:
            with open(args.path, "rb") as stream:
                document = read_plan(stream)
        report = review_plan(document)
    except (PlanReviewError, OSError) as error:
        message = str(error) if isinstance(error, PlanReviewError) else "Could not read the plan file. Check that it exists and is readable."
        if args.json:
            print(json.dumps({"status": "error", "message": message}))
        else:
            print("Plan review error: " + message, file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else format_review(report))
    return 0
