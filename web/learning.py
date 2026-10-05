"""Curated mission coaching; no shell, AWS access, or learner file paths.

The catalog is loaded from one fixed authored file. Hints and answer keys stay
server-side until their dedicated methods are called. These are teaching checks,
not automated checks of a learner's AWS account.
"""
from copy import deepcopy
import json
from pathlib import Path

if __package__:
    from .catalog import read_regular_file
else:
    from catalog import read_regular_file


class LearningCatalog:
    def __init__(self, root):
        self._lessons = json.loads(read_regular_file(Path(root).resolve(), "web/playbooks.json"))
        if not isinstance(self._lessons, dict):
            raise ValueError("Invalid learning catalog")

    def _lesson(self, lab_id):
        if not isinstance(lab_id, str) or lab_id not in self._lessons:
            raise ValueError("Unknown mission")
        return self._lessons[lab_id]

    def public_lesson(self, lab_id):
        lesson = deepcopy(self._lesson(lab_id))
        for stage in lesson["stages"]:
            stage["hintCount"] = len(stage.pop("hints", []))
        for question in lesson["questions"]:
            question.pop("correctIndex", None)
            question.pop("explanation", None)
        return lesson

    def hint(self, lab_id, stage_id, level):
        lesson = self._lesson(lab_id)
        stage = next((stage for stage in lesson["stages"] if stage["id"] == stage_id), None)
        if stage is None:
            raise ValueError("Unknown stage")
        hints = stage["hints"]
        if type(level) is not int or not 1 <= level <= len(hints):
            raise ValueError("Hint level is out of range")
        return {**deepcopy(hints[level - 1]), "level": level, "total": len(hints)}

    def check_answer(self, lab_id, question_id, answer_index):
        lesson = self._lesson(lab_id)
        question = next((q for q in lesson["questions"] if q["id"] == question_id), None)
        if question is None:
            raise ValueError("Unknown question")
        if type(answer_index) is not int or not 0 <= answer_index < len(question["options"]):
            raise ValueError("Answer index is out of range")
        return {"correct": answer_index == question["correctIndex"], "explanation": question["explanation"]}
