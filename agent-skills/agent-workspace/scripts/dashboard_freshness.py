"""Check dashboard inputs and keep generated files out of the local Git index."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from catalog_client import list_records, run_catalog
from list_workspace_tasks import discover


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def metadata_path(output: Path) -> Path:
    return output.with_suffix(".dashboard.json")


def atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as pending:
        temporary = Path(pending.name)
        try:
            pending.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def refresh_catalog(workspace: Path, *, folder_scope: bool = False) -> None:
    def run(*args: str) -> None:
        result = run_catalog(*args)
        if result.returncode:
            raise ValueError("dashboard discovery refresh failed: " + (result.stderr or result.stdout).strip())

    if folder_scope:
        tasks = [r for r in list_records() if r.get("kind") in {"agent-task", "workspace-task"}
                 and Path(r["path"]).resolve().is_relative_to(workspace)]
    else:
        run("register", "--path", str(workspace))
        tasks, _ = discover(workspace)
    roots = [workspace]
    for task in tasks:
        path = Path(task["path"])
        if path.is_dir():
            run("register", "--path", str(path))
        if path.is_dir() and not path.is_relative_to(workspace) and path not in roots:
            roots.append(path)
    run("reconcile", *(str(root) for root in roots), "--format", "json")


def input_fingerprint(snapshot: dict, sources: list[Path]) -> str:
    stable = {key: value for key, value in snapshot.items() if key != "generated_at"}
    stable["tasks"] = [
        {key: value for key, value in task.items() if key != "last_seen"}
        for task in snapshot["tasks"]
    ]
    files = [Path(snapshot["workspace"]) / "workspace.yaml", *sources]
    linked_files = {}
    for task in snapshot["tasks"]:
        folder = Path(task["path"])
        files.append(folder / "README.md")
        for field in ("objective", "current_state", "next_task"):
            for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", task.get(field, "")):
                try:
                    parsed = urlsplit(target.strip().removeprefix("<").removesuffix(">"))
                except ValueError:
                    continue
                if not parsed.scheme and not parsed.netloc:
                    path = (folder / unquote(parsed.path or "README.md")).resolve()
                    linked_files[str(path)] = path.exists()
    stable["files"] = {str(path): sha256(path) for path in files}
    stable["linked_files"] = linked_files
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def check_report(output: Path, snapshot: dict, fingerprint: str, max_age_minutes: float) -> dict:
    payload = {
        "operation": "dashboard", "outcome": "checked", "output": str(output),
        "task_count": len(snapshot["tasks"]), "freshness": "stale", "reasons": [],
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "max_age_minutes": max_age_minutes,
    }
    if not output.is_file():
        return {**payload, "freshness": "missing", "reasons": ["report_missing"]}
    try:
        metadata = json.loads(metadata_path(output).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(metadata["generated_at"])
        if generated.tzinfo is None or metadata["schema_version"] != 1:
            raise ValueError("invalid timestamp or schema")
        age = (datetime.now(timezone.utc) - generated).total_seconds()
        payload.update(generated_at=metadata["generated_at"], age_seconds=round(age))
        if age < 0:
            payload["reasons"].append("clock_changed")
        elif age >= max_age_minutes * 60:
            payload["reasons"].append("age_limit_exceeded")
        if metadata["input_fingerprint"] != fingerprint:
            payload["reasons"].append("inputs_changed")
        if metadata["output_sha256"] != sha256(output):
            payload["reasons"].append("report_changed")
        if metadata["max_age_minutes"] != max_age_minutes:
            payload["reasons"].append("age_limit_changed")
    except (OSError, ValueError, KeyError, TypeError):
        payload["reasons"].append("metadata_missing_or_invalid")
    if not payload["reasons"]:
        payload["freshness"] = "current"
    return payload


def exclude_generated(output: Path) -> dict:
    """Add exact paths to this checkout's Git excludes; preserve tracked files."""
    output = output.resolve()
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(output.parent), *args],
                              capture_output=True, text=True, check=False)

    try:
        result = git("rev-parse", "--show-toplevel")
    except OSError:
        return {"status": "unavailable", "warning": "Git is unavailable; ignore rules were not written."}
    if result.returncode:
        return {"status": "outside_repository"}
    root = Path(result.stdout.strip()).resolve()
    paths = [output, metadata_path(output), output.parent / (output.stem + "-assets")]
    relative = [path.relative_to(root).as_posix() for path in paths]
    tracked = [name for name in relative if git("ls-files", "--", ":(top,literal)" + name).stdout.strip()]
    result = git("rev-parse", "--git-path", "info/exclude")
    if result.returncode:
        raise ValueError("cannot locate Git exclude file: " + result.stderr.strip())
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = output.parent / exclude
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    patterns = ["/" + re.sub(r"([\\*?!\[\]# ])", r"\\\1", name) for name in relative]
    patterns[-1] += "/"
    additions = [pattern for pattern in patterns if pattern not in existing.splitlines()]
    if additions:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write(("\n" if existing and not existing.endswith("\n") else "")
                         + "# Generated workspace dashboard\n" + "\n".join(additions) + "\n")
    if tracked:
        return {"status": "already_tracked", "warning": "Git still tracks these paths: " + ", ".join(tracked)}
    return {"status": "ignored", "exclude_file": str(exclude.resolve())}
