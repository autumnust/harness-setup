#!/usr/bin/env python3
"""Create, list, and reconcile portable agent-task folders."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload.get("ok"):
        if payload.get("operation") == "agent-task-set-state":
            print(f"Task state: {payload['status']}")
        print(f"Task folder: {payload['path']}")
        if payload.get("catalog_warning"):
            print(f"Catalog refresh warning: {payload['catalog_warning']}")
        return
    print(f"Task folder: {payload.get('path', 'not created')}")
    print(f"Error: {payload['error']}", file=sys.stderr)


def init_task(arguments: argparse.Namespace) -> int:
    try:
        hydrate = helper("agent-task") / "scripts" / "hydrate_task.py"
    except ValueError as exc:
        emit(
            {
                "schema_version": 2,
                "operation": "agent-task-init",
                "ok": False,
                "path": "",
                "catalog_registered": False,
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
                "schema_version": 2,
                "operation": "agent-task-init",
                "ok": False,
                "path": path,
                "catalog_registered": registered,
                "error": error,
            },
            arguments.format,
        )
        return 2 if path else 1

    payload = {
        "schema_version": 2,
        "operation": "agent-task-init",
        "ok": True,
        "path": path,
        "catalog_registered": True,
    }
    emit(payload, arguments.format)
    return 0


ACTIVE_STATUSES = {"active", "paused", "waiting", "blocked"}
TERMINAL_STATUSES = {"done", "cancelled"}
STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES
LEGACY_RUNTIME_FIELDS = {
    "runtime_host",
    "tmux_session",
    "tss_host",
    "tss_target",
    "session_name",
}


def yaml_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else str(decoded)
    return value


def yaml_scalar(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_front_matter(text: str) -> tuple[dict[str, str], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("task README.md has no YAML front matter")
    end = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if end is None:
        raise ValueError("task README.md has unterminated YAML front matter")
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = yaml_unquote(value)
    return metadata, end


def replace_front_matter(text: str, updates: dict[str, str | None]) -> str:
    _metadata, end = parse_front_matter(text)
    lines = text.splitlines()
    pending = dict(updates)
    remove_indexes: list[int] = []
    for index in range(1, end):
        if ":" not in lines[index]:
            continue
        key = lines[index].split(":", 1)[0].strip()
        if key not in pending:
            continue
        value = pending.pop(key)
        if value is None:
            remove_indexes.append(index)
        else:
            lines[index] = f"{key}: {yaml_scalar(value)}"
    for index in reversed(remove_indexes):
        del lines[index]
        end -= 1
    lines[end:end] = [
        f"{key}: {yaml_scalar(value)}"
        for key, value in pending.items()
        if value is not None
    ]
    return "\n".join(lines).rstrip() + "\n"


def replace_markdown_section(text: str, title: str, content: str) -> str:
    lines = text.splitlines()
    heading = f"## {title}"
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading), None
    )
    replacement = [heading, "", content.strip()]
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.extend(["", *replacement])
    else:
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if lines[index].startswith("## ")
            ),
            len(lines),
        )
        lines[start:end] = replacement + ([""] if end < len(lines) else [])
    return "\n".join(lines).rstrip() + "\n"


def remove_markdown_section(text: str, title: str) -> str:
    lines = text.splitlines()
    heading = f"## {title}"
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading), None
    )
    if start is None:
        return text
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    del lines[start:end]
    return "\n".join(lines).rstrip() + "\n"


def atomic_write(readme: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="README.", suffix=".tmp", dir=readme.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text)
        os.chmod(temporary_name, readme.stat().st_mode & 0o777)
        os.replace(temporary_name, readme)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def catalog_command(executable: Path | None) -> list[str]:
    if executable is not None:
        return [str(executable)]
    installed = harness_home() / "bin" / "task-catalog"
    if installed.is_file():
        return [str(installed)]
    return [sys.executable, str(source_root() / "scripts" / "task-catalog.py")]


def set_task_state(arguments: argparse.Namespace) -> int:
    task_dir = arguments.task_dir.expanduser().resolve()
    readme = task_dir / "README.md"
    try:
        if not readme.is_file():
            raise ValueError(f"task directory has no README.md: {task_dir}")
        if not arguments.summary.strip():
            raise ValueError("--summary cannot be empty")
        if arguments.status in ACTIVE_STATUSES and not (
            arguments.next_step and arguments.next_step.strip()
        ):
            raise ValueError(
                f"{arguments.status} requires --next-step with a concrete action or resume trigger"
            )
        original = readme.read_text(encoding="utf-8")
        metadata, _end = parse_front_matter(original)
        if metadata.get("agent_task") != "1" and metadata.get("workspace_task") != "1":
            raise ValueError("README.md is not an agent-task or workspace task record")
        if not metadata.get("id"):
            raise ValueError("task README.md needs a stable id")

        changed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        updates: dict[str, str | None] = {
            "status": arguments.status,
            "updated": changed_at[:10],
            "last_used_at": changed_at,
            "state_changed_at": changed_at,
            "completed": changed_at if arguments.status in TERMINAL_STATUSES else None,
        }
        updates.update({field: None for field in LEGACY_RUNTIME_FIELDS})
        updated = replace_front_matter(original, updates)
        updated = replace_markdown_section(updated, "Current state", arguments.summary)
        if arguments.status in TERMINAL_STATUSES:
            updated = replace_markdown_section(updated, "Outcome", arguments.summary)
            updated = replace_markdown_section(
                updated,
                "Immediate next task",
                "No further work is recorded for this task.",
            )
        else:
            updated = remove_markdown_section(updated, "Outcome")
            updated = replace_markdown_section(
                updated, "Immediate next task", arguments.next_step
            )
        atomic_write(readme, updated)
    except (OSError, UnicodeError, ValueError) as exc:
        emit(
            {
                "schema_version": 2,
                "operation": "agent-task-set-state",
                "ok": False,
                "path": str(task_dir),
                "error": str(exc),
            },
            arguments.format,
        )
        return 1

    register_code, _record, register_error = run_json(
        [
            *catalog_command(arguments.catalog_cli),
            "register",
            "--path",
            str(task_dir),
            "--format",
            "json",
        ]
    )
    warning = register_error if register_code else ""
    emit(
        {
            "schema_version": 2,
            "operation": "agent-task-set-state",
            "ok": True,
            "path": str(task_dir),
            "status": arguments.status,
            "updated_at": changed_at,
            "catalog_registered": register_code == 0,
            "catalog_warning": warning,
        },
        arguments.format,
    )
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

    init_parser = subparsers.add_parser("init", help="create and register a task")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--objective", default="Define the objective.")
    init_parser.add_argument("--destination", required=True, type=Path)
    init_parser.add_argument("--catalog-cli", type=Path)
    add_output_format(
        init_parser,
        choices=("text", "json", "human"),
        default="text",
    )
    init_parser.set_defaults(handler=init_task)

    state_parser = subparsers.add_parser(
        "set-state", help="record an explicit lifecycle change"
    )
    state_parser.add_argument("--task-dir", required=True, type=Path)
    state_parser.add_argument("--status", required=True, choices=tuple(sorted(STATUSES)))
    state_parser.add_argument("--summary", required=True)
    state_parser.add_argument("--next-step")
    state_parser.add_argument("--catalog-cli", type=Path, help=argparse.SUPPRESS)
    add_output_format(
        state_parser,
        choices=("text", "json", "human"),
        default="text",
    )
    state_parser.set_defaults(handler=set_task_state)

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
