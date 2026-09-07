#!/usr/bin/env python3
"""List cataloged task records and optionally verify their TSS sessions."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catalog_client import catalog_executable, list_records


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


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    status: str
    task: str
    workspace: str
    target: str
    execution_folder: str
    present: bool


def text_value(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            return value
    return ""


def records() -> list[TaskRecord]:
    catalog_records = list_records()
    workspace_paths: dict[str, list[str]] = {}
    for record in catalog_records:
        if record.get("kind") != "workspace" or not record.get("present", True):
            continue
        workspace_id = text_value(record, "id", "workspace_id")
        workspace_path = text_value(record, "path", "local_path")
        if workspace_id and workspace_path:
            workspace_paths.setdefault(workspace_id, []).append(workspace_path)

    found: list[TaskRecord] = []
    for record in catalog_records:
        if record.get("kind") not in {"agent-task", "workspace-task"}:
            continue
        workspace = text_value(record, "workspace_path")
        workspace_id = text_value(record, "workspace_id")
        if not workspace and workspace_id:
            candidates = sorted(set(workspace_paths.get(workspace_id, [])))
            if len(candidates) == 1:
                workspace = candidates[0]
        host = text_value(record, "runtime_host", "host")
        session = text_value(record, "tmux_session")
        target = text_value(record, "tss_target")
        if not target and host and session:
            target = f"{host}:{session}"
        path = text_value(record, "path", "local_path")
        found.append(
            TaskRecord(
                task_id=text_value(record, "id", "task_id"),
                status=text_value(record, "status") or "unknown",
                task=text_value(record, "task_name", "name", "title")
                or Path(path).name,
                workspace=workspace,
                target=target or "not recorded",
                execution_folder=path,
                present=bool(record.get("present", True)),
            )
        )
    return sorted(
        found,
        key=lambda item: (STATUS_ORDER.get(item.status, 99), item.task.casefold()),
    )


def live_sessions(host: str) -> tuple[set[str] | None, str]:
    if shutil.which("tss") is None:
        return None, "tss is not installed"
    try:
        result = subprocess.run(
            ["tss", host],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if result.returncode != 0:
        detail = result.stdout.strip().splitlines()
        return None, detail[-1] if detail else f"exit {result.returncode}"
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    sessions: set[str] = set()
    for line in clean.splitlines():
        match = re.match(rf"^\s*{re.escape(host)}\s+(\S+)\s+", line)
        if match:
            sessions.add(match.group(1))
    return sessions, ""


def tss_states(items: list[TaskRecord], validate: bool) -> dict[str, str]:
    states = {item.target: "not checked" for item in items}
    if not validate:
        return states
    by_host: dict[str, set[str]] = {}
    for item in items:
        if item.target == "not recorded":
            states[item.target] = "not recorded"
            continue
        host, session = item.target.split(":", 1)
        by_host.setdefault(host, set()).add(session)
    for host, requested in by_host.items():
        sessions, error = live_sessions(host)
        for session in requested:
            target = f"{host}:{session}"
            displayed = sessions or set()
            is_present = session in displayed or any(
                name.endswith("…") and session.startswith(name[:-1])
                for name in displayed
            )
            states[target] = (
                "unknown"
                if sessions is None
                else ("present" if is_present else "missing")
            )
        if sessions is None:
            print(f"warning: tss {host}: {error}", file=sys.stderr)
    return states


def recreate(item: TaskRecord) -> None:
    if item.status in {"done", "cancelled", "archived"}:
        raise ValueError(f"cannot recreate terminal task {item.task!r} ({item.status})")
    if not item.present:
        raise ValueError(f"task folder is not present on this host: {item.execution_folder}")
    if item.target == "not recorded":
        raise ValueError(f"task {item.task!r} has no recorded TSS target")
    helper = (
        Path(__file__).resolve().parents[2]
        / "task-session"
        / "scripts"
        / "start_task_session.py"
    )
    if not helper.is_file():
        raise ValueError(f"task-session helper is unavailable: {helper}")
    host, session = item.target.split(":", 1)
    command = [
        sys.executable,
        str(helper),
        "--task-dir",
        item.execution_folder,
        "--tss-host",
        host,
        "--session-name",
        session,
        "--format",
        "json",
    ]
    if item.workspace:
        command.extend(("--workspace", item.workspace))
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise ValueError(f"could not recreate task {item.task!r}: {detail}")
    print(f"Recreated {item.target} in {item.workspace or item.execution_folder}.")


def markdown(items: list[TaskRecord], states: dict[str, str], checked: bool) -> str:
    verification = "live TSS checked" if checked else "catalog records only"
    lines = [
        f"Catalog: `{catalog_executable()}` ({verification})",
        "",
        "| Status | Task | Workspace | Recorded TSS target | TSS state | Execution folder | Present |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        cells = (
            item.status,
            item.task,
            item.workspace or "—",
            item.target,
            states[item.target],
            item.execution_folder,
            "yes" if item.present else "no",
        )
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    if len(lines) == 4:
        return "\n".join(lines[:2] + ["\nNo task records found."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--config", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--validate-tss", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument(
        "--task", action="append", help="task name to recreate; repeat for several tasks"
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    arguments = parser.parse_args()
    try:
        items = records()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if arguments.recreate:
        if not arguments.task:
            parser.error("--recreate requires at least one --task")
        selected_names = set(arguments.task)
        selected = [item for item in items if item.task in selected_names]
        missing_names = selected_names - {item.task for item in selected}
        if missing_names:
            print(
                f"error: task records not found: {', '.join(sorted(missing_names))}",
                file=sys.stderr,
            )
            return 1
        try:
            for item in selected:
                recreate(item)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        items = selected
    checked = arguments.validate_tss or arguments.recreate
    states = tss_states(items, checked)
    if arguments.format == "json":
        payload = {
            "catalog": str(catalog_executable()),
            "schema_version": 2,
            "tss_checked": checked,
            "tasks": [
                {
                    "id": item.task_id,
                    "status": item.status,
                    "task": item.task,
                    "workspace": item.workspace,
                    "tss_target": item.target,
                    "tss_state": states[item.target],
                    "execution_folder": item.execution_folder,
                    "present": item.present,
                }
                for item in items
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(markdown(items, states, checked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
