#!/usr/bin/env python3
"""List agent-task workspaces registered in the machine-local task catalog."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalog_client import CatalogError, run_catalog_json


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


def string_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return str(value)
    return ""


def normalize_record(record: dict[str, Any]) -> dict[str, str]:
    return {
        "id": string_value(record, "id", "task_id") or "unknown",
        "title": string_value(record, "title", "name") or "unknown",
        "status": string_value(record, "status") or "unknown",
        "created": string_value(record, "created", "created_at"),
        "updated": string_value(record, "updated", "updated_at"),
        "objective": string_value(record, "objective"),
        "current_state": string_value(record, "current_state"),
        "next_task": string_value(record, "next_task"),
        "path": string_value(record, "path", "local_path"),
    }


def path_is_within(path: str, roots: list[Path]) -> bool:
    if not roots:
        return True
    try:
        candidate = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    return any(candidate == root or candidate.is_relative_to(root) for root in roots)


def records_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records")
    if not isinstance(records, list):
        raise CatalogError("task catalog JSON does not contain a records list")
    return [record for record in records if isinstance(record, dict)]


def discover(*, catalog_cli: Path | None, roots: list[Path]) -> list[dict[str, str]]:
    # Keep this invocation fixed. SQL selection belongs to task-catalog itself.
    payload = run_catalog_json(
        ("list", "--format", "json", "--kind", "agent-task"),
        executable=catalog_cli,
    )
    resolved_roots = [root.expanduser().resolve() for root in roots]
    tasks = [
        normalize_record(record)
        for record in records_from_payload(payload)
        if string_value(record, "kind", "task_kind") in {"", "agent-task"}
        and path_is_within(string_value(record, "path", "local_path"), resolved_roots)
    ]
    return sorted(
        tasks,
        key=lambda task: (
            STATUS_ORDER.get(task["status"], STATUS_ORDER["unknown"]),
            task["title"].casefold(),
        ),
    )


def reconcile(*, catalog_cli: Path | None, roots: list[Path]) -> dict[str, Any]:
    if not roots:
        raise CatalogError("reconciliation requires at least one root")
    return run_catalog_json(
        (
            "reconcile",
            *(str(root.expanduser().resolve()) for root in roots),
            "--format",
            "json",
        ),
        executable=catalog_cli,
    )


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(tasks: list[dict[str, str]]) -> str:
    if not tasks:
        return "No agent-task workspaces found."
    lines = [
        "| Status | Task | Updated | Immediate next task | Path |",
        "| --- | --- | --- | --- | --- |",
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
                    "next_task",
                    "path",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def render_human(tasks: list[dict[str, str]]) -> str:
    if not tasks:
        return "No general tasks found."
    lines = [f"General tasks: {len(tasks)}"]
    for task in tasks:
        status = " ".join(task["status"].split()) or "unknown"
        lines.extend(("", f"[{status}] {' '.join(task['title'].split())}"))
        details = []
        if task["updated"]:
            details.append(f"updated {task['updated']}")
        if details:
            lines.append("  " + " | ".join(details))
        lines.append(f"  Path: {task['path']}")
        if task["next_task"]:
            lines.append(
                textwrap.fill(
                    " ".join(task["next_task"].split()),
                    width=100,
                    initial_indent="  Next: ",
                    subsequent_indent="        ",
                )
            )
    return "\n".join(lines)


def render_json(roots: list[Path], tasks: list[dict[str, str]]) -> str:
    payload: dict[str, Any] = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "task-catalog",
        "roots": [str(root.expanduser().resolve()) for root in roots],
        "tasks": tasks,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="optional local path filters; no filesystem scan is performed",
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
    parser.add_argument(
        "--catalog-cli",
        type=Path,
        help="task-catalog executable (defaults to the installed harness command)",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="explicitly scan the given roots through task-catalog before listing",
    )
    args = parser.parse_args()
    try:
        if args.reconcile:
            reconcile(catalog_cli=args.catalog_cli, roots=args.roots)
        tasks = discover(catalog_cli=args.catalog_cli, roots=args.roots)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(render_json(args.roots, tasks))
    elif args.format == "human":
        print(render_human(tasks))
    else:
        print(render_markdown(tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
