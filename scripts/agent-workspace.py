#!/usr/bin/env python3
"""Create and operate portable agent workspaces through deterministic helpers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any


def source_root() -> Path:
    script = Path(__file__).resolve()
    repository = script.parent.parent
    if (repository / "agent-skills" / "agent-workspace").is_dir():
        return repository
    harness_home = Path(
        os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
    ).expanduser()
    deployed = harness_home / "current" / "source"
    if (deployed / "agent-skills" / "agent-workspace").is_dir():
        return deployed
    raise ValueError("cannot locate deployed agent-workspace helpers")


def helper(root: Path, skill: str, name: str) -> Path:
    path = root / "agent-skills" / skill / "scripts" / name
    if not path.is_file():
        raise ValueError(f"required helper is unavailable: {path}")
    return path


def run_helper(path: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), *arguments],
        check=False,
        text=True,
        capture_output=True,
    )


def json_output(result: subprocess.CompletedProcess[str], operation: str) -> dict[str, Any]:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise ValueError(f"{operation} failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{operation} returned a non-object JSON value")
    return payload


def optional_path(arguments: list[str], flag: str, value: Path | None) -> None:
    if value is not None:
        arguments.extend((flag, str(value)))


def registration_status(payload: dict[str, Any]) -> int:
    return 0 if payload.get("catalog_registered") is True else 2


def run_init(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    command = [
        "--name",
        args.name,
        "--destination",
        str(args.destination),
        "--format",
        "json",
    ]
    for repository in args.repo:
        command.extend(("--repo", repository))
    result = run_helper(
        helper(root, "agent-workspace", "hydrate_workspace.py"), command
    )
    payload = json_output(result, "workspace initialization")
    payload["operation"] = "init"
    status = registration_status(payload)
    payload["outcome"] = "complete" if status == 0 else "partial"
    return payload, status


def run_rehydrate(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    result = run_helper(
        helper(root, "agent-workspace", "hydrate_workspace.py"),
        [
            "--rehydrate-from",
            str(args.manifest),
            "--destination",
            str(args.destination),
            "--format",
            "json",
        ],
    )
    payload = json_output(result, "workspace rehydration")
    payload["operation"] = "rehydrate"
    status = registration_status(payload)
    payload["outcome"] = "complete" if status == 0 else "partial"
    return payload, status


def run_list(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    command = ["--workspace", str(args.workspace), "--format", "json"]
    for status in args.status:
        command.extend(("--status", status))
    result = run_helper(
        helper(root, "agent-workspace", "list_workspace_tasks.py"), command
    )
    payload = json_output(result, "workspace task listing")
    payload["operation"] = "list-tasks"
    payload["outcome"] = "complete"
    return payload, 0


def run_start_task(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], int]:
    initialize_command = [
        "--workspace",
        str(args.workspace),
        "--name",
        args.name,
        "--objective",
        args.objective or f"Complete {args.name}.",
        "--format",
        "json",
    ]
    optional_path(initialize_command, "--config", args.config)
    optional_path(initialize_command, "--execution-root", args.execution_root)
    optional_path(initialize_command, "--execution-folder", args.execution_folder)
    initialized = run_helper(
        helper(root, "agent-workspace", "start_workspace_task.py"),
        initialize_command,
    )
    task = json_output(initialized, "workspace task initialization")
    status = registration_status(task)
    payload = {
        "operation": "start-task",
        "outcome": "complete" if status == 0 else "partial",
        "task": task,
    }
    return payload, status


def add_format(parser: argparse.ArgumentParser) -> None:
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--format", choices=("text", "json", "human"))
    formats.add_argument(
        "-H",
        "--human",
        dest="format",
        action="store_const",
        const="human",
        help="show compact output for terminal reading",
    )
    parser.set_defaults(format="text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-workspace", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init", help="create a workspace")
    initialize.add_argument("--name", required=True)
    initialize.add_argument("--destination", required=True, type=Path)
    initialize.add_argument(
        "--repo",
        action="append",
        default=[],
        required=True,
        help="name|url|branch|role; repeat for multiple repositories",
    )
    add_format(initialize)

    rehydrate = subparsers.add_parser(
        "rehydrate", help="rehydrate a workspace from workspace.yaml"
    )
    rehydrate.add_argument("--manifest", required=True, type=Path)
    rehydrate.add_argument("--destination", required=True, type=Path)
    add_format(rehydrate)

    start = subparsers.add_parser(
        "start-task", help="create and register a workspace task"
    )
    start.add_argument("--workspace", required=True, type=Path)
    start.add_argument("--name", required=True)
    start.add_argument("--objective")
    start.add_argument("--config", type=Path)
    start.add_argument("--execution-root", type=Path)
    start.add_argument("--execution-folder", type=Path)
    add_format(start)

    listing = subparsers.add_parser("list-tasks", help="list workspace tasks")
    listing.add_argument("--workspace", required=True, type=Path)
    listing.add_argument(
        "--status",
        action="append",
        default=[],
        choices=("blocked", "active", "waiting", "paused", "done", "cancelled", "archived", "unknown"),
    )
    add_format(listing)
    return parser


def render_text(payload: dict[str, Any]) -> str:
    operation = payload["operation"]
    if operation in {"init", "rehydrate"}:
        lines = [str(payload["workspace"])]
        if payload.get("outcome") == "partial":
            lines.append(f"Catalog registration failed: {payload.get('catalog_warning', '')}")
        return "\n".join(lines)
    if operation == "list-tasks":
        tasks = payload.get("tasks", [])
        if not tasks:
            return "No workspace tasks found."
        return "\n".join(
            f"{task['status']:10} {task['task_name']}  {task['path']}" for task in tasks
        )
    task = payload["task"]
    lines = [f"Execution folder: {task['execution_folder']}"]
    if payload.get("outcome") == "partial":
        lines.append(
            "Catalog registration failed: " + str(task.get("catalog_warning", ""))
        )
    return "\n".join(lines)


def render_human(payload: dict[str, Any]) -> str:
    if payload["operation"] != "list-tasks":
        return render_text(payload)
    tasks = payload.get("tasks", [])
    workspace = str(payload.get("workspace", ""))
    if not tasks:
        return f"No tasks found for {workspace}." if workspace else "No workspace tasks found."
    lines = [f"Workspace tasks: {len(tasks)}"]
    if workspace:
        lines.append(f"Workspace: {workspace}")
    for task in tasks:
        status = " ".join(str(task.get("status", "unknown")).split()) or "unknown"
        name = " ".join(str(task.get("task_name", "")).split())
        missing = " [missing]" if str(task.get("present", "1")) == "0" else ""
        lines.extend(("", f"[{status}] {name}{missing}"))
        details = []
        if task.get("last_used_at"):
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
        lines.append(f"  Path: {task.get('path', '')}")
    return "\n".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        root = source_root()
        if args.command == "init":
            payload, status = run_init(args, root)
        elif args.command == "rehydrate":
            payload, status = run_rehydrate(args, root)
        elif args.command == "list-tasks":
            payload, status = run_list(args, root)
        else:
            payload, status = run_start_task(args, root)
    except (OSError, ValueError) as exc:
        if getattr(args, "format", "text") == "json":
            print(json.dumps({"error": str(exc), "operation": args.command}, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.format == "human":
        print(render_human(payload))
    else:
        print(render_text(payload))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
