"""Shared, stateless teaching operations over fixed authored simulations.

Commands in the catalog are display text. This module never executes them or
reads learner plans. Feedback describes an authored case, not a live system.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from web.catalog import read_regular_file


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (("practice/cases.json", "investigation"), ("practice/plan-drills.json", "plan"))
CARD_FIELDS = ("id", "kind", "title", "summary", "minutes", "skills", "relatedLabs", "provenance")
DEBRIEF_FIELDS = ("explanation", "decisiveEvidence", "repair", "verification", "cleanup", "followUp")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MISSION = re.compile(r"\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*(?:/scenario-\d{2})?\Z")


def _require(condition):
    if not condition:
        raise ValueError("Invalid authored drill catalog; check the shared drill schema and references")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _slug(value):
    return isinstance(value, str) and SLUG.fullmatch(value) is not None


def _unique(items, field):
    _require(all(isinstance(item, dict) and _slug(item.get(field)) for item in items))
    identifiers = [item[field] for item in items]
    _require(len(identifiers) == len(set(identifiers)))
    return set(identifiers)


def _validate(drill, kind, root):
    _require(isinstance(drill, dict) and _slug(drill.get("id")) and drill.get("kind") == kind)
    _require(all(_text(drill.get(field)) for field in ("title", "summary", "brief", "provenance")))
    _require(type(drill.get("minutes")) is int and drill["minutes"] > 0)
    skills = drill.get("skills")
    _require(isinstance(skills, list) and bool(skills) and all(_slug(skill) for skill in skills))
    labs = drill.get("relatedLabs")
    _require(isinstance(labs, list) and bool(labs))
    for lab in labs:
        _require(isinstance(lab, str) and MISSION.fullmatch(lab) is not None)
        try:
            read_regular_file(root, f"labs/{lab}/README.md")
        except ValueError as exc:
            raise ValueError("Invalid authored drill catalog; related mission is unavailable") from exc
    observations = drill.get("observations")
    _require(isinstance(observations, list) and bool(observations))
    observation_ids = _unique(observations, "id")
    _require(all(all(_text(item.get(field)) for field in ("label", "command", "output")) for item in observations))
    question = drill.get("question")
    _require(isinstance(question, dict) and _text(question.get("prompt")))
    options = question.get("options")
    _require(isinstance(options, list) and len(options) >= 2)
    option_ids = _unique(options, "id")
    _require(all(_text(option.get("text")) for option in options))
    solution = drill.get("answer")
    _require(isinstance(solution, dict) and _slug(solution.get("optionId")))
    _require(solution["optionId"] in option_ids)
    _require(all(_text(solution.get(field)) for field in DEBRIEF_FIELDS if field != "decisiveEvidence"))
    decisive = solution.get("decisiveEvidence")
    _require(isinstance(decisive, list) and bool(decisive) and all(_slug(item) for item in decisive))
    _require(len(decisive) == len(set(decisive)) and set(decisive).issubset(observation_ids))


def _load(root):
    drills = {}
    for relative, kind in SOURCES:
        try:
            document = json.loads(read_regular_file(root, relative))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Cannot read authored drill catalog: {relative}") from exc
        _require(isinstance(document, dict) and type(document.get("schemaVersion")) is int and document["schemaVersion"] == 1)
        _require(isinstance(document.get("drills"), list))
        for drill in document["drills"]:
            _validate(drill, kind, root)
            _require(drill["id"] not in drills)
            drills[drill["id"]] = drill
    return drills


def _drill(drill_id, root):
    if not _slug(drill_id):
        raise ValueError("Unknown drill")
    drill = _load(root).get(drill_id)
    if drill is None:
        raise ValueError("Unknown drill")
    return drill


def _pick(source, fields):
    return deepcopy({field: source[field] for field in fields})


def list_drills(root=ROOT):
    """Return only card metadata for both drill kinds, in authored order."""
    return {"schemaVersion": 1, "drills": [_pick(drill, CARD_FIELDS) for drill in _load(root).values()]}


def public_drill(drill_id, root=ROOT):
    """Return the brief and choices without outputs or answer metadata."""
    drill = _drill(drill_id, root)
    return {
        **_pick(drill, CARD_FIELDS + ("brief",)),
        "observations": [_pick(item, ("id", "label", "command")) for item in drill["observations"]],
        "question": {"prompt": drill["question"]["prompt"],
                     "options": [_pick(option, ("id", "text")) for option in drill["question"]["options"]]},
    }


def evidence(drill_id, evidence_id, root=ROOT):
    """Reveal exactly one requested authored observation."""
    drill = _drill(drill_id, root)
    if _slug(evidence_id):
        for item in drill["observations"]:
            if item["id"] == evidence_id:
                return {"drillId": drill_id, **_pick(item, ("id", "label", "command", "output")),
                        "provenance": drill["provenance"]}
    raise ValueError("Unknown observation")


def answer(drill_id, option_id, root=ROOT):
    """Return simulated feedback after a valid choice; do not save an attempt."""
    drill = _drill(drill_id, root)
    if not _slug(option_id) or option_id not in {option["id"] for option in drill["question"]["options"]}:
        raise ValueError("Unknown answer option")
    solution = drill["answer"]
    return {"drillId": drill_id, "optionId": option_id,
            "correct": option_id == solution["optionId"], "correctOptionId": solution["optionId"],
            **_pick(solution, DEBRIEF_FIELDS), "provenance": drill["provenance"]}
