#!/usr/bin/env python3
"""Record an explicit task lifecycle change in the task file and tmux."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from start_task_session import (
    existing_task_id,
    parse_front_matter,
    run_tmux,
    session_exists,
    yaml_scalar,
)


ACTIVE_STATUSES = {"active", "paused", "waiting", "blocked"}
TERMINAL_STATUSES = {"done", "cancelled"}
STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES


def replace_front_matter(
    text: str, updates: dict[str, str | None]
) -> str:
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
        (index for index, line in enumerate(lines) if line.strip() == heading),
        None,
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
        (index for index, line in enumerate(lines) if line.strip() == heading),
        None,
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


def write_task_record(readme: Path, text: str) -> None:
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


def update_session_state(
    socket_name: str | None,
    session_name: str,
    task_id: str,
    status: str,
    changed_at: str,
) -> tuple[bool, str]:
    if not session_exists(socket_name, session_name):
        return False, f"tmux session is not running: {session_name}"
    owner = existing_task_id(socket_name, session_name)
    if owner != task_id:
        return False, f"tmux session belongs to another or unrecorded task: {session_name}"
    try:
        for key, value in (
            ("@agent_task_status", status),
            ("@agent_task_state_changed_at", changed_at),
        ):
            run_tmux(socket_name, "set-option", "-t", session_name, key, value)
        if status in TERMINAL_STATUSES:
            run_tmux(
                socket_name,
                "set-option",
                "-t",
                session_name,
                "@agent_task_finished_at",
                changed_at,
            )
        else:
            run_tmux(
                socket_name,
                "set-option",
                "-u",
                "-t",
                session_name,
                "@agent_task_finished_at",
                check=False,
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        return False, f"could not update tmux task state: {detail.strip()}"
    return True, ""


def set_task_state(
    task_dir: Path,
    status: str,
    summary: str,
    next_step: str | None = None,
    socket_name: str | None = None,
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    readme = task_dir / "README.md"
    if not readme.is_file():
        raise ValueError(f"task directory has no README.md: {task_dir}")
    if status not in STATUSES:
        raise ValueError(f"unsupported task status: {status}")
    if not summary.strip():
        raise ValueError("state summary cannot be empty")
    if status in ACTIVE_STATUSES and not (next_step and next_step.strip()):
        raise ValueError(f"{status} requires a concrete next step or resume trigger")

    original = readme.read_text(encoding="utf-8")
    metadata, _end = parse_front_matter(original)
    if metadata.get("agent_task") != "1" and metadata.get("workspace_task") != "1":
        raise ValueError("task README is not an agent-task or workspace task record")
    task_id = metadata.get("id")
    if not task_id:
        raise ValueError("task README front matter needs a stable id")

    changed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    updated = replace_front_matter(
        original,
        {
            "status": status,
            "updated": changed_at[:10],
            "state_changed_at": changed_at,
            "completed": changed_at if status in TERMINAL_STATUSES else None,
        },
    )
    updated = replace_markdown_section(updated, "Current state", summary)
    if status in TERMINAL_STATUSES:
        updated = replace_markdown_section(updated, "Outcome", summary)
        updated = replace_markdown_section(
            updated, "Immediate next task", "No further work is recorded for this task."
        )
    else:
        updated = remove_markdown_section(updated, "Outcome")
        updated = replace_markdown_section(updated, "Immediate next task", next_step or "")
    write_task_record(readme, updated)

    session_name = metadata.get("tmux_session", "")
    session_marked = False
    session_warning = ""
    if session_name:
        session_marked, session_warning = update_session_state(
            socket_name, session_name, task_id, status, changed_at
        )
    else:
        session_warning = "task has no recorded tmux session"

    return {
        "changed_at": changed_at,
        "completed": changed_at if status in TERMINAL_STATUSES else "",
        "next_step": next_step or "",
        "outcome": summary if status in TERMINAL_STATUSES else "",
        "session_marked": session_marked,
        "session_name": session_name,
        "session_warning": session_warning,
        "status": status,
        "summary": summary,
        "task_dir": str(task_dir),
        "task_id": task_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--status", required=True, choices=sorted(STATUSES))
    parser.add_argument("--summary", required=True)
    parser.add_argument("--next-step")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--tmux-socket", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    try:
        result = set_task_state(
            arguments.task_dir,
            arguments.status,
            arguments.summary,
            next_step=arguments.next_step,
            socket_name=arguments.tmux_socket,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Task marked {result['status']}.")
        print(f"Task record: {result['task_dir']}")
        if result["session_marked"]:
            print(f"Session state updated: {result['session_name']}")
        else:
            print(f"Session state not updated: {result['session_warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
