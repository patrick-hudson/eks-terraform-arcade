"""Public launch metadata only; never reads learner workspaces or runs commands."""
import json
from pathlib import Path

if __package__:
    from .catalog import read_regular_file
else:
    from catalog import read_regular_file


def public_recipe(root, lab_id):
    data = json.loads(read_regular_file(Path(root).resolve(), "lab-recipes.json"))
    if data.get("schemaVersion") != 1 or not isinstance(lab_id, str):
        raise ValueError("Unsupported launch catalog")
    recipe = next((item for item in data["recipes"] if item["id"] == lab_id), None)
    if recipe is None:
        raise ValueError("Unknown mission")
    public = {key: recipe[key] for key in (
        "id", "alias", "title", "kind", "runDirectory", "prerequisites", "cost")}
    public["environmentPrerequisites"] = recipe.get("environmentPrerequisites", recipe["prerequisites"])
    public["modes"] = {key: {field: mode[field] for field in ("label", "description")}
                       for key, mode in recipe["modes"].items()}
    return public
