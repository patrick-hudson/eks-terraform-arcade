#!/usr/bin/env python3
"""Practice an authored investigation without executing its displayed commands."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import drill_engine


def _human(action, result):
    if action == "list":
        print("Offline practice — authored simulations; no AWS access")
        for drill in result["drills"]:
            print(f"{drill['id']}  {drill['title']} ({drill['kind']}, {drill['minutes']} min)")
        print("Next: arcade drill show ID")
    elif action == "show":
        print(f"{result['title']}\n\n{result['provenance']}\n\n{result['brief']}")
        print("\nObservations (displayed commands are never executed):")
        for item in result["observations"]:
            print(f"  {item['id']}: {item['label']}\n    {item['command']}")
        print(f"\n{result['question']['prompt']}")
        for option in result["question"]["options"]:
            print(f"  {option['id']}: {option['text']}")
        print(f"\nReveal: arcade drill evidence {result['id']} EVIDENCE_ID")
        print(f"Decide: arcade drill answer {result['id']} OPTION_ID")
        print("Related missions: " + ", ".join(result["relatedLabs"]))
    elif action == "evidence":
        print(f"{result['label']}\n{result['provenance']}\n\nDisplay only: {result['command']}\n\n{result['output']}")
    else:
        print("Fits this simulation." if result["correct"] else "Reconsider this simulation using the evidence below.")
        print(f"\n{result['explanation']}\n\nDecisive observations: {', '.join(result['decisiveEvidence'])}")
        for field, label in (("repair", "Terraform repair"), ("verification", "Recovery evidence and limits"),
                             ("cleanup", "Cleanup"), ("followUp", "Changed constraint")):
            print(f"\n{label}: {result[field]}")
        print(f"\n{result['provenance']}\nCLI practice is stateless; browser attempts are stored by the browser.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit stable JSON")
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ("list", "show", "evidence", "answer"):
        command = actions.add_parser(action)
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit stable JSON")
        if action != "list":
            command.add_argument("id", help="Drill ID")
        if action in ("evidence", "answer"):
            command.add_argument("selection", help="Observation ID" if action == "evidence" else "Answer option ID")
    args = parser.parse_args(argv)
    try:
        if args.action == "list":
            result = drill_engine.list_drills()
        elif args.action == "show":
            result = drill_engine.public_drill(args.id)
        elif args.action == "evidence":
            result = drill_engine.evidence(args.id, args.selection)
        else:
            result = drill_engine.answer(args.id, args.selection)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, sort_keys=True))
        else:
            print(f"Drill error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _human(args.action, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
