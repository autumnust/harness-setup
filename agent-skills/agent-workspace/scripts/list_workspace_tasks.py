#!/usr/bin/env python3
"""List cataloged task locations for one initialized agent workspace."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalog_client import list_records
from start_workspace_task import workspace_identity


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


def text_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            return value
    return ""


def normalize_record(record: dict[str, Any]) -> dict[str, str]:
    task_name = text_value(record, "task_name", "name", "title")
    path = text_value(record, "path", "local_path")
    present = record.get("present", True)
    return {
        "created": text_value(record, "created"),
        "history_only": "",
        "id": text_value(record, "id", "task_id"),
        "last_used_at": text_value(record, "last_used", "last_used_at", "updated"),
        "path": path,
        "present": "1" if present else "0",
        "status": text_value(record, "status") or "unknown",
        "task_name": task_name or Path(path).name,
        "updated": text_value(record, "updated"),
    }


def discover(
    workspace: Path,
    statuses: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    workspace = workspace.expanduser().resolve()
    _workspace_name, workspace_id = workspace_identity(workspace / "workspace.yaml")
    if not workspace_id:
        matching = [
            record
            for record in list_records("--kind", "workspace")
            if Path(text_value(record, "path", "local_path")).expanduser().resolve()
            == workspace
        ]
        workspace_ids = {
            text_value(record, "id", "workspace_id") for record in matching
        } - {""}
        if len(workspace_ids) != 1:
            raise ValueError(
                "legacy workspace is not registered at its current local path"
            )
        workspace_id = workspace_ids.pop()
    raw = list_records(
        "--kind",
        "workspace-task",
        "--workspace-id",
        workspace_id,
    )
    tasks = [normalize_record(record) for record in raw]
    if statuses is not None:
        tasks = [task for task in tasks if task["status"] in statuses]
    tasks.sort(
        key=lambda task: (task["last_used_at"], task["task_name"].casefold()),
        reverse=True,
    )
    missing_paths = sorted(
        task["path"] for task in tasks if task["present"] == "0" and task["path"]
    )
    return tasks, missing_paths


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(tasks: list[dict[str, str]], missing_paths: list[str]) -> str:
    if not tasks:
        output = "No workspace tasks found."
    else:
        lines = [
            "| Task | Status | Last used | Path |",
            "| --- | --- | --- | --- |",
        ]
        for task in tasks:
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(task[key])
                    for key in (
                        "task_name",
                        "status",
                        "last_used_at",
                        "path",
                    )
                )
                + " |"
            )
        output = "\n".join(lines)
    if missing_paths:
        output += "\n\nMissing registered execution folders:\n"
        output += "\n".join(f"- `{path}`" for path in missing_paths)
    return output


def render_human(
    workspace: Path,
    tasks: list[dict[str, str]],
    missing_paths: list[str],
) -> str:
    if not tasks:
        return f"No tasks found for {workspace}."
    lines = [f"Workspace tasks: {len(tasks)}", f"Workspace: {workspace}"]
    for task in tasks:
        missing = " [missing]" if task["present"] == "0" else ""
        status = " ".join(task["status"].split()) or "unknown"
        lines.extend(("", f"[{status}] {' '.join(task['task_name'].split())}{missing}"))
        details = []
        if task["last_used_at"]:
            details.append(f"last used {task['last_used_at']}")
        if details:
            lines.append(
                textwrap.fill(
                    " | ".join(details),
                    width=100,
                    initial_indent="  ",
                    subsequent_indent="  ",
                )
            )
        lines.append(f"  Path: {task['path']}")
    if missing_paths:
        lines.extend(("", f"Missing folders: {len(missing_paths)}"))
    return "\n".join(lines)


def render_json(
    workspace: Path,
    tasks: list[dict[str, str]],
    missing_paths: list[str],
) -> str:
    return json.dumps(
        {
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace": str(workspace),
            "tasks": tasks,
            "missing_paths": missing_paths,
        },
        indent=2,
        sort_keys=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--execution-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--status",
        action="append",
        choices=tuple(STATUS_ORDER),
        help="include only this task status; repeat to include several",
    )
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--format", choices=("markdown", "json", "human"))
    formats.add_argument(
        "-H",
        "--human",
        dest="format",
        action="store_const",
        const="human",
        help="show compact records for terminal reading",
    )
    parser.set_defaults(format="markdown")
    arguments = parser.parse_args()
    try:
        workspace = arguments.workspace.expanduser().resolve()
        statuses = set(arguments.status) if arguments.status else None
        tasks, missing_paths = discover(workspace, statuses)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(render_json(workspace, tasks, missing_paths))
    elif arguments.format == "human":
        print(render_human(workspace, tasks, missing_paths))
    else:
        print(render_markdown(tasks, missing_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
