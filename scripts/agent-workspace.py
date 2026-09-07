#!/usr/bin/env python3
"""Create and operate portable agent workspaces through deterministic helpers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def run_init(args: argparse.Namespace, root: Path) -> dict[str, Any]:
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
    return payload


def run_rehydrate(args: argparse.Namespace, root: Path) -> dict[str, Any]:
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
    return payload


def run_list(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    command = ["--workspace", str(args.workspace), "--format", "json"]
    for status in args.status:
        command.extend(("--status", status))
    result = run_helper(
        helper(root, "agent-workspace", "list_workspace_tasks.py"), command
    )
    payload = json_output(result, "workspace task listing")
    payload["operation"] = "list-tasks"
    return payload


def run_start_task(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], bool]:
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

    session_command = [
        "--task-dir",
        str(task["execution_folder"]),
        "--workspace",
        str(args.workspace),
        "--format",
        "json",
    ]
    optional_path(session_command, "--config", args.config)
    if args.tss_host:
        session_command.extend(("--tss-host", args.tss_host))
    if args.session_name:
        session_command.extend(("--session-name", args.session_name))
    if args.tmux_socket:
        session_command.extend(("--tmux-socket", args.tmux_socket))
    started = run_helper(
        helper(root, "task-session", "start_task_session.py"), session_command
    )
    payload: dict[str, Any] = {
        "operation": "start-task",
        "session_started": started.returncode == 0,
        "task": task,
    }
    if started.returncode == 0:
        payload["session"] = json_output(started, "task session start")
        payload["session_error"] = ""
        return payload, True
    payload["session"] = None
    payload["session_error"] = (
        started.stderr or started.stdout or f"exit {started.returncode}"
    ).strip()
    return payload, False


def add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init", help="create a workspace")
    initialize.add_argument("--name", required=True)
    initialize.add_argument("--destination", required=True, type=Path)
    initialize.add_argument("--repo", action="append", default=[], required=True)
    add_format(initialize)

    rehydrate = subparsers.add_parser(
        "rehydrate", help="rehydrate a workspace from workspace.yaml"
    )
    rehydrate.add_argument("--manifest", required=True, type=Path)
    rehydrate.add_argument("--destination", required=True, type=Path)
    add_format(rehydrate)

    start = subparsers.add_parser(
        "start-task", help="create a workspace task and start its tmux session"
    )
    start.add_argument("--workspace", required=True, type=Path)
    start.add_argument("--name", required=True)
    start.add_argument("--objective")
    start.add_argument("--config", type=Path)
    start.add_argument("--execution-root", type=Path)
    start.add_argument("--execution-folder", type=Path)
    start.add_argument("--tss-host")
    start.add_argument("--session-name")
    start.add_argument("--tmux-socket", help=argparse.SUPPRESS)
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
        return str(payload["workspace"])
    if operation == "list-tasks":
        tasks = payload.get("tasks", [])
        if not tasks:
            return "No workspace tasks found."
        return "\n".join(
            f"{task['status']:10} {task['task_name']}  {task['path']}" for task in tasks
        )
    task = payload["task"]
    lines = [f"Execution folder: {task['execution_folder']}"]
    if payload["session_started"]:
        lines.append(f"Connect: tss {payload['session']['tss_target']}")
    else:
        lines.append(f"Session start failed: {payload['session_error']}")
    return "\n".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        root = source_root()
        succeeded = True
        if args.command == "init":
            payload = run_init(args, root)
        elif args.command == "rehydrate":
            payload = run_rehydrate(args, root)
        elif args.command == "list-tasks":
            payload = run_list(args, root)
        else:
            payload, succeeded = run_start_task(args, root)
    except (OSError, ValueError) as exc:
        if getattr(args, "format", "text") == "json":
            print(json.dumps({"error": str(exc), "operation": args.command}, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
