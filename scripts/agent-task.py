#!/usr/bin/env python3
"""Create, list, and reconcile portable agent-task folders."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


def harness_home() -> Path:
    return Path(
        os.environ.get("AGENT_HARNESS_HOME", str(Path.home() / ".agent-harness"))
    ).expanduser().resolve()


def source_root() -> Path:
    checkout = Path(__file__).resolve().parents[1]
    if (checkout / "agent-skills" / "agent-task").is_dir():
        return checkout
    installed = harness_home() / "current" / "source"
    if (installed / "agent-skills" / "agent-task").is_dir():
        return installed
    raise ValueError(
        "cannot locate harness source; reinstall the harness or set AGENT_HARNESS_HOME"
    )


def helper(name: str) -> Path:
    return source_root() / "agent-skills" / name


def run_json(command: Sequence[str]) -> tuple[int, dict[str, Any], str]:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        return 1, {}, str(exc)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    detail = result.stderr.strip()
    if result.returncode and not detail:
        detail = result.stdout.strip() or f"command exited with {result.returncode}"
    return result.returncode, payload, detail


def config_tss_host(config_path: Path | None) -> str | None:
    path = config_path or harness_home() / "config.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime configuration {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"runtime configuration must contain an object: {path}")
    task_runtime = payload.get("task_runtime")
    if not isinstance(task_runtime, dict):
        return None
    tss = task_runtime.get("tss")
    if not isinstance(tss, dict):
        return None
    host = tss.get("host_alias")
    return host if isinstance(host, str) and host else None


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload.get("ok"):
        print(f"Task folder: {payload['path']}")
        print(f"Connect: tss {payload['tss_target']}")
        return
    print(f"Task folder: {payload.get('path', 'not created')}")
    print(f"Error: {payload['error']}", file=sys.stderr)


def init_task(arguments: argparse.Namespace) -> int:
    try:
        tss_host = arguments.tss_host or config_tss_host(arguments.config)
        if not tss_host:
            raise ValueError(
                "TSS host label is unresolved; pass --tss-host or configure "
                "task_runtime.tss.host_alias"
            )
        hydrate = helper("agent-task") / "scripts" / "hydrate_task.py"
        session = arguments.task_session_cli or (
            helper("task-session") / "scripts" / "start_task_session.py"
        )
    except ValueError as exc:
        emit(
            {
                "schema_version": 1,
                "operation": "agent-task-init",
                "ok": False,
                "path": "",
                "catalog_registered": False,
                "session_started": False,
                "error": str(exc),
            },
            arguments.format,
        )
        return 1

    hydrate_command = [
        sys.executable,
        str(hydrate),
        "--name",
        arguments.name,
        "--objective",
        arguments.objective,
        "--destination",
        str(arguments.destination),
        "--format",
        "json",
    ]
    if arguments.catalog_cli:
        hydrate_command.extend(["--catalog-cli", str(arguments.catalog_cli)])
    hydrate_code, hydration, hydrate_error = run_json(hydrate_command)
    path = str(hydration.get("path", ""))
    registered = hydration.get("catalog_registered") is True
    if hydrate_code or not path or not registered:
        error = (
            str(hydration.get("registration_error", ""))
            or hydrate_error
            or "task creation did not return a registered folder"
        )
        emit(
            {
                "schema_version": 1,
                "operation": "agent-task-init",
                "ok": False,
                "path": path,
                "catalog_registered": registered,
                "session_started": False,
                "error": error,
            },
            arguments.format,
        )
        return 2 if path else 1

    session_command = [
        sys.executable,
        str(session),
        "--task-dir",
        path,
        "--tss-host",
        tss_host,
        "--format",
        "json",
    ]
    if arguments.session_name:
        session_command.extend(["--session-name", arguments.session_name])
    if arguments.config:
        session_command.extend(["--config", str(arguments.config)])
    if arguments.tmux_socket:
        session_command.extend(["--tmux-socket", arguments.tmux_socket])
    session_code, session_result, session_error = run_json(session_command)
    if session_code:
        emit(
            {
                "schema_version": 1,
                "operation": "agent-task-init",
                "ok": False,
                "path": path,
                "catalog_registered": True,
                "session_started": False,
                "error": session_error or "task session setup failed",
            },
            arguments.format,
        )
        return 3

    if session_result.get("catalog_registered") is not True:
        error = str(session_result.get("catalog_warning", "")) or (
            "task session started but catalog runtime refresh failed"
        )
        emit(
            {
                "schema_version": 1,
                "operation": "agent-task-init",
                "ok": False,
                "path": path,
                "catalog_registered": False,
                "session_started": True,
                "session_name": str(session_result.get("session_name", "")),
                "tss_target": str(session_result.get("tss_target", "")),
                "error": error,
            },
            arguments.format,
        )
        return 2

    payload = {
        "schema_version": 1,
        "operation": "agent-task-init",
        "ok": True,
        "path": path,
        "catalog_registered": True,
        "session_started": True,
        "session_created": bool(session_result.get("created")),
        "session_name": str(session_result.get("session_name", "")),
        "tss_host": str(session_result.get("tss_host", tss_host)),
        "tss_target": str(session_result.get("tss_target", "")),
    }
    emit(payload, arguments.format)
    return 0


def run_discovery(arguments: argparse.Namespace, *, do_reconcile: bool) -> int:
    try:
        discover = helper("agent-task") / "scripts" / "discover_tasks.py"
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    command = [sys.executable, str(discover), *(str(root) for root in arguments.roots)]
    if do_reconcile:
        command.append("--reconcile")
    command.extend(["--format", arguments.format])
    if arguments.catalog_cli:
        command.extend(["--catalog-cli", str(arguments.catalog_cli)])
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def add_output_format(
    parser: argparse.ArgumentParser,
    *,
    choices: tuple[str, ...],
    default: str,
) -> None:
    formats = parser.add_mutually_exclusive_group()
    formats.add_argument("--format", choices=choices)
    formats.add_argument(
        "-H",
        "--human",
        dest="format",
        action="store_const",
        const="human",
        help="show compact output for terminal reading",
    )
    parser.set_defaults(format=default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create, register, and start a task")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--objective", default="Define the objective.")
    init_parser.add_argument("--destination", required=True, type=Path)
    init_parser.add_argument("--tss-host")
    init_parser.add_argument("--session-name")
    init_parser.add_argument("--config", type=Path)
    init_parser.add_argument("--catalog-cli", type=Path)
    add_output_format(
        init_parser,
        choices=("text", "json", "human"),
        default="text",
    )
    init_parser.add_argument("--task-session-cli", type=Path, help=argparse.SUPPRESS)
    init_parser.add_argument("--tmux-socket", help=argparse.SUPPRESS)
    init_parser.set_defaults(handler=init_task)

    list_parser = subparsers.add_parser("list", help="list registered tasks")
    list_parser.add_argument("roots", nargs="*", type=Path)
    list_parser.add_argument("--catalog-cli", type=Path)
    add_output_format(
        list_parser,
        choices=("markdown", "json", "human"),
        default="markdown",
    )
    list_parser.set_defaults(handler=lambda args: run_discovery(args, do_reconcile=False))

    reconcile_parser = subparsers.add_parser(
        "reconcile", help="scan selected roots and update registrations"
    )
    reconcile_parser.add_argument("roots", nargs="+", type=Path)
    reconcile_parser.add_argument("--catalog-cli", type=Path)
    add_output_format(
        reconcile_parser,
        choices=("markdown", "json", "human"),
        default="markdown",
    )
    reconcile_parser.set_defaults(
        handler=lambda args: run_discovery(args, do_reconcile=True)
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    return int(arguments.handler(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
