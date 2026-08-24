#!/usr/bin/env python3
"""Discover agent-task workspaces and summarize their live filesystem state."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", ".venv", "__pycache__", "node_modules",
}
STATUS_ORDER = {
    "blocked": 0,
    "active": 1,
    "waiting": 2,
    "paused": 3,
    "done": 4,
    "cancelled": 5,
    "archived": 6,
    "unknown": 7,
}


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}, text
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, "\n".join(lines[end + 1 :])


def markdown_section(text: str, title: str) -> str:
    lines = text.splitlines()
    heading = f"## {title}".casefold()
    start = next(
        (index + 1 for index, line in enumerate(lines) if line.strip().casefold() == heading),
        None,
    )
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            collected.append(line.strip())
    return " ".join(collected)


def task_from_readme(readme: Path) -> dict[str, str] | None:
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    metadata, body = parse_front_matter(text)
    if metadata.get("agent_task") != "1":
        return None
    runtime_host = metadata.get("runtime_host", "")
    tmux_session = metadata.get("tmux_session", "")
    return {
        "id": metadata.get("id", "unknown"),
        "title": metadata.get("title", readme.parent.name),
        "status": metadata.get("status", "unknown"),
        "created": metadata.get("created", ""),
        "updated": metadata.get("updated", ""),
        "runtime_host": runtime_host,
        "tmux_session": tmux_session,
        "tss_target": (
            f"{runtime_host}:{tmux_session}"
            if runtime_host and tmux_session
            else ""
        ),
        "objective": markdown_section(body, "Current objective"),
        "current_state": markdown_section(body, "Current state"),
        "next_task": markdown_section(body, "Immediate next task"),
        "path": str(readme.parent.resolve()),
    }


def discover(roots: list[Path]) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    seen: set[Path] = set()
    for raw_root in roots:
        root = raw_root.expanduser().resolve()
        if not root.is_dir() or root in seen:
            continue
        seen.add(root)
        for current, directories, files in os.walk(root):
            directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
            if "README.md" not in files:
                continue
            task = task_from_readme(Path(current) / "README.md")
            if task is not None:
                tasks.append(task)
                directories[:] = []
    return sorted(
        tasks,
        key=lambda task: (
            STATUS_ORDER.get(task["status"], STATUS_ORDER["unknown"]),
            task["title"].casefold(),
        ),
    )


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(tasks: list[dict[str, str]]) -> str:
    if not tasks:
        return "No agent-task workspaces found."
    lines = [
        "| Status | Task | Updated | Session | Immediate next task | Path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        lines.append(
            "| "
            + " | ".join(
                escape_cell(task[key])
                for key in (
                    "status",
                    "title",
                    "updated",
                    "tss_target",
                    "next_task",
                    "path",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def render_json(roots: list[Path], tasks: list[dict[str, str]]) -> str:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [str(root.expanduser().resolve()) for root in roots],
        "tasks": tasks,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    roots = args.roots or [Path.home() / "Documents"]
    tasks = discover(roots)
    print(render_json(roots, tasks) if args.format == "json" else render_markdown(tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
