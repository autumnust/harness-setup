#!/usr/bin/env python3
"""List filesystem-backed task records and optionally verify their TSS sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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
    status: str
    task: str
    workspace: str
    target: str
    execution_folder: str


def yaml_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        return decoded if isinstance(decoded, str) else value
    return value


def front_matter(readme: Path) -> dict[str, str]:
    try:
        lines = readme.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = yaml_unquote(value)
    return metadata


def configured_root(config: Path | None) -> Path:
    if config is None:
        harness_home = Path(os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness"))
        config = harness_home / "config.json"
    try:
        payload = json.loads(config.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime configuration {config}: {exc}") from exc
    root = payload.get("execution_root") if isinstance(payload, dict) else None
    if not isinstance(root, str) or not root:
        raise ValueError("runtime configuration has no execution_root; pass --execution-root")
    path = Path(root).expanduser()
    if not path.is_absolute():
        raise ValueError(f"configured execution_root must be absolute: {path}")
    return path.resolve()


def records(root: Path) -> list[TaskRecord]:
    found: list[TaskRecord] = []
    for readme in root.rglob("README.md"):
        metadata = front_matter(readme)
        is_agent_task = metadata.get("agent_task") == "1"
        is_workspace_task = metadata.get("workspace_task") == "1"
        if not is_agent_task and not is_workspace_task:
            continue
        host = metadata.get("runtime_host", "")
        session = metadata.get("tmux_session", "")
        found.append(
            TaskRecord(
                status=metadata.get("status", "unknown"),
                task=metadata.get("task_name", metadata.get("title", readme.parent.name)),
                workspace=metadata.get("workspace_path", ""),
                target=f"{host}:{session}" if host and session else "not recorded",
                execution_folder=str(readme.parent.resolve()),
            )
        )
    return sorted(found, key=lambda item: (STATUS_ORDER.get(item.status, 99), item.task.casefold()))


def live_sessions(host: str) -> tuple[set[str] | None, str]:
    if shutil.which("tss") is None:
        return None, "tss is not installed"
    try:
        result = subprocess.run(
            ["tss", host], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, result.stdout.strip().splitlines()[-1] if result.stdout.strip() else f"exit {result.returncode}"
    clean = re.sub(r"\\x1b\\[[0-9;]*m", "", result.stdout)
    sessions: set[str] = set()
    for line in clean.splitlines():
        match = re.match(rf"^\\s*{re.escape(host)}\\s+(\\S+)\\s+", line)
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
            states[target] = "unknown" if sessions is None else ("present" if session in sessions else "missing")
        if sessions is None:
            print(f"warning: tss {host}: {error}", file=sys.stderr)
    return states


def markdown(items: list[TaskRecord], states: dict[str, str], root: Path, checked: bool) -> str:
    verification = "live TSS checked" if checked else "filesystem records only"
    lines = [
        f"Execution root: `{root}` ({verification})",
        "",
        "| Status | Task | Workspace | Recorded TSS target | TSS state | Execution folder |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        cells = (item.status, item.task, item.workspace or "—", item.target, states[item.target], item.execution_folder)
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    if len(lines) == 4:
        return "\n".join(lines[:2] + ["\nNo task records found."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--validate-tss", action="store_true")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    arguments = parser.parse_args()
    try:
        root = arguments.execution_root.expanduser().resolve() if arguments.execution_root else configured_root(arguments.config)
        if not root.is_dir():
            raise ValueError(f"execution root is not a directory: {root}")
        items = records(root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    states = tss_states(items, arguments.validate_tss)
    if arguments.format == "json":
        payload = {
            "execution_root": str(root),
            "tss_checked": arguments.validate_tss,
            "tasks": [
                {
                    "status": item.status,
                    "task": item.task,
                    "workspace": item.workspace,
                    "tss_target": item.target,
                    "tss_state": states[item.target],
                    "execution_folder": item.execution_folder,
                }
                for item in items
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(markdown(items, states, root, arguments.validate_tss))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
