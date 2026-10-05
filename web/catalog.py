"""Build a spoiler-conscious catalog from authored learning-kit files.

MANIFEST.sha256 supplies the file inventory, not an integrity lock: learners may
edit authored examples locally. Runtime files never enter the source API merely
because they were created underneath the project directory.
"""
import os
from pathlib import Path, PurePosixPath
import re
import stat


LANGUAGES = {".md": "markdown", ".tf": "hcl", ".hcl": "hcl", ".yaml": "yaml", ".yml": "yaml", ".py": "python", ".sh": "bash"}
EXCLUDED_DIRECTORIES = {"run", "work", "state", "plans", "outputs", "__pycache__", "node_modules"}
TRACKS = {"00": "Terraform", "01": "AWS", "02": "Terraform", "03": "AWS", "04": "AWS", "05": "AWS", "06": "Terraform", "07": "Kubernetes", "08": "Kubernetes", "09": "Kubernetes", "10": "Kubernetes", "11": "Kubernetes", "12": "Capstone", "13": "Kubernetes"}
TAG_TERMS = ("Terraform", "S3", "IAM", "Lambda", "DynamoDB", "VPC", "EKS", "Kubernetes", "RBAC", "Pod Identity", "EBS", "CSI", "import", "drift", "locking", "Service", "replica", "maintenance")


class FileNotAllowed(ValueError):
    """A requested path is outside the explicit authored-file surface."""


def canonical_path(relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or any(ord(c) < 32 for c in relative):
        raise FileNotAllowed("Invalid source path")
    path = PurePosixPath(relative)
    if path.is_absolute() or str(path) != relative or any(part in (".", "..") for part in path.parts):
        raise FileNotAllowed("Invalid source path")
    return path


def read_regular_file(root, relative):
    """Read through directory descriptors, refusing symlinks at every step.

O_NOFOLLOW also protects a source replaced by a symlink after catalog creation.
O_NONBLOCK avoids hanging if an allowed regular file is replaced by a FIFO.
"""
    path = canonical_path(relative)
    directory = None
    file_descriptor = None
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in path.parts[:-1]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        file_descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(file_descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4 * 1024 * 1024:
            raise FileNotAllowed("Source must be a small regular file")
        with os.fdopen(file_descriptor, "rb") as source:
            file_descriptor = None
            return source.read(4 * 1024 * 1024 + 1)
    except OSError as error:
        raise FileNotAllowed("Source is unavailable") from error
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if directory is not None:
            os.close(directory)


def authored_path(relative):
    try:
        path = canonical_path(relative)
    except FileNotAllowed:
        return False
    if any(part.startswith(".") or part in EXCLUDED_DIRECTORIES for part in path.parts):
        return False
    if any(marker in path.name.lower() for marker in (".tfstate", ".tfplan", ".tfvars")):
        return False
    if path.suffix not in LANGUAGES:
        return False
    module_source = relative.startswith("modules/kubernetes-exercise/") and path.suffix in {".tf", ".md"}
    return relative == "README.md" or path.parts[0] in {"labs", "docs", "scripts"} or module_source


def regular_without_links(root, relative):
    current = root
    try:
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.is_symlink():
                return False
        return current.is_file()
    except OSError:
        return False


def plain_text(text):
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*`_]", "", text).strip()


def title_from_readme(content):
    heading = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), "Learning guide")
    return re.sub(r"^(?:Game\s+)?\d{2}\s*[·—–-]\s*", "", heading)


def summary_from_readme(content):
    paragraphs = re.split(r"\n\s*\n", content)
    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if not stripped or stripped.startswith(("#", "```", "|", "- ")):
            continue
        if stripped.startswith("**"):
            # Introductory bold metadata ends before the actual assignment.
            if "**Time box:" in stripped:
                continue
            closing = stripped.find("**", 2)
            if closing >= 0:
                stripped = stripped[closing + 2:].strip()
        if stripped:
            return plain_text(" ".join(stripped.split()))
    return ""


def cost_from_readme(content, number, scenario=False):
    if scenario:
        return "No new AWS services; existing Game 07 cluster."
    intro = "\n".join(content.splitlines()[:8])
    clean = plain_text(intro)
    # Preserve cost wording from the source, including qualifications and units.
    labeled = re.search(r"(?:Incremental AWS cost|Incremental cost|Cost):\s*([^\n]+)", clean)
    if labeled:
        return labeled.group(1).split(". ", 1)[0].rstrip(".")
    bold = re.search(r"\*\*(.+?)\*\*", intro)
    if bold:
        for segment in plain_text(bold.group(1)).split("·"):
            if "$" in segment or "cost" in segment.lower():
                return segment.strip().rstrip(".")
    if number == "11":
        return "Existing Game 07 cluster; see cost guide."
    if number == "12":
        return "Uses the whole-curriculum $20 allowance; see cost guide."
    return "See mission and cost guide."


class Catalog:
    def __init__(self, root):
        self.root = Path(root).resolve()
        inventory = read_regular_file(self.root, "MANIFEST.sha256").decode("utf-8")
        candidates = set()
        for line in inventory.splitlines():
            match = re.fullmatch(r"[a-fA-F0-9]{64} [ *](.+)", line)
            if match and authored_path(match.group(1)):
                candidates.add(match.group(1))
        # The guide is added with this web UI, after the original kit manifest.
        candidates.add("docs/web-ui.md")
        self.allowed_paths = frozenset(path for path in candidates if regular_without_links(self.root, path))

    def read_file(self, relative):
        canonical_path(relative)
        if relative not in self.allowed_paths:
            raise FileNotAllowed("Source is not in the authored-file allowlist")
        try:
            content = read_regular_file(self.root, relative).decode("utf-8")
        except UnicodeError as error:
            raise FileNotAllowed("Source must be UTF-8 text") from error
        return {"path": relative, "content": content, "language": LANGUAGES.get(PurePosixPath(relative).suffix, "text")}

    def _root_table(self):
        rows = {}
        if "README.md" not in self.allowed_paths:
            return rows
        for line in self.read_file("README.md")["content"].splitlines():
            match = re.search(r"\[(\d{2})\]\(labs/[^)]+/README\.md\)", line)
            cells = [plain_text(cell) for cell in line.strip("|").split("|")]
            if match and len(cells) == 4:
                rows[match.group(1)] = {"duration": cells[2], "mode": cells[3]}
        return rows

    def _entry(self, directory, metadata, scenario=False):
        readme = f"{directory}/README.md"
        content = self.read_file(readme)["content"]
        number = directory.rsplit("/", 1)[-1][:2]
        if scenario:
            number = directory.rsplit("-", 1)[-1]
        intro = "\n".join(content.splitlines()[:12])
        duration_match = re.search(r"(\d+(?:[–-]\d+)?)\s*minutes", intro)
        duration = duration_match.group(0) if duration_match else metadata.get("duration", "See mission")
        files = []
        prefix = directory + "/"
        for path in sorted(self.allowed_paths):
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix):]
            if relative in {"README.md", "HINTS.md", "ANSWERS.md"} or (not scenario and relative.startswith("scenario-")):
                continue
            parts = PurePosixPath(relative).parts
            kind = "solution" if any(part in {"solution", "refactor"} for part in parts) else "starter" if any(part in {"starter", "broken"} for part in parts) else "other"
            files.append({"path": path, "name": relative, "kind": kind, "language": LANGUAGES[PurePosixPath(path).suffix]})
        return {
            "id": directory.removeprefix("labs/"),
            "number": number,
            "title": f"Incident {number}" if scenario else title_from_readme(content),
            "summary": summary_from_readme(content),
            "track": "Kubernetes" if scenario else TRACKS.get(number, "AWS"),
            "mode": "Broken start" if scenario else metadata.get("mode", "Build and debug"),
            "duration": duration,
            "cost": cost_from_readme(content, number, scenario),
            "tags": [term for term in TAG_TERMS if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", intro, re.IGNORECASE)],
            "readme": readme,
            "hints": f"{directory}/HINTS.md" if f"{directory}/HINTS.md" in self.allowed_paths else None,
            "answers": f"{directory}/ANSWERS.md" if f"{directory}/ANSWERS.md" in self.allowed_paths else None,
            "files": files,
            "scenarios": [],
        }

    def build(self):
        metadata = self._root_table()
        labs = []
        for path in sorted(self.allowed_paths):
            if not re.fullmatch(r"labs/\d{2}-[^/]+/README\.md", path):
                continue
            directory = path.removesuffix("/README.md")
            number = directory.split("/")[1][:2]
            entry = self._entry(directory, metadata.get(number, {}))
            scenario_paths = sorted(p for p in self.allowed_paths if re.fullmatch(re.escape(directory) + r"/scenario-\d{2}/README\.md", p))
            entry["scenarios"] = [self._entry(p.removesuffix("/README.md"), {}, scenario=True) for p in scenario_paths]
            labs.append(entry)
        docs = []
        for path in sorted(self.allowed_paths):
            if path == "README.md" or (path.startswith("docs/") and path.endswith(".md")):
                docs.append({"id": "overview" if path == "README.md" else PurePosixPath(path).stem, "title": title_from_readme(self.read_file(path)["content"]), "path": path})
        return {"schemaVersion": 1, "labs": labs, "docs": docs}
