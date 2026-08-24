#!/usr/bin/env python3
"""List execution folders that belong to one initialized agent workspace."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def parse_front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(
            index for index in range(1, len(lines)) if lines[index].strip() == "---"
        )
    except StopIteration:
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = yaml_unquote(value)
    return metadata


def workspace_identity(workspace_file: Path) -> tuple[str, str]:
    lines = workspace_file.read_text(encoding="utf-8").splitlines()
    in_workspace = False
    name = ""
    workspace_id = ""
    for line in lines:
        if line.strip() == "workspace:":
            in_workspace = True
            continue
        if in_workspace and not line.startswith((" ", "\t")):
            break
        if in_workspace and ":" in line:
            key, value = line.strip().split(":", 1)
            if key == "name":
                name = yaml_unquote(value)
            elif key == "id":
                workspace_id = yaml_unquote(value)
    if not name:
        raise ValueError(f"workspace name is missing from {workspace_file}")
    return name, workspace_id


def config_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    harness_home = Path(
        os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
    ).expanduser()
    return harness_home / "config.json"


def configured_execution_root(explicit_config: Path | None) -> Path | None:
    path = config_path(explicit_config)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime configuration {path}: {exc}") from exc
    root = payload.get("execution_root") if isinstance(payload, dict) else None
    if not isinstance(root, str) or not root:
        return None
    resolved = Path(root).expanduser()
    if not resolved.is_absolute():
        raise ValueError(f"configured execution_root must be absolute: {resolved}")
    return resolved.resolve()


def indexed_paths(workspace: Path) -> list[Path]:
    index = workspace / ".git" / "agent-workspace" / "task-paths.json"
    if not index.is_file():
        return []
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read workspace task index {index}: {exc}") from exc
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(f"workspace task index has an invalid paths list: {index}")
    return [Path(path).expanduser() for path in paths]


def task_from_path(
    task_dir: Path,
    workspace: Path,
    workspace_title: str,
    workspace_id: str,
) -> dict[str, str] | None:
    readme = task_dir / "README.md"
    if not readme.is_file():
        return None
    try:
        metadata = parse_front_matter(readme.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return None
    if metadata.get("workspace_task") != "1":
        return None
    recorded_id = metadata.get("workspace_id", "")
    recorded_path = metadata.get("workspace_path", "")
    if workspace_id and recorded_id:
        if recorded_id != workspace_id:
            return None
    elif recorded_path and Path(recorded_path).expanduser().resolve() == workspace:
        pass
    elif metadata.get("workspace") != workspace_title:
        return None
    runtime_host = metadata.get("runtime_host", "")
    tmux_session = metadata.get("tmux_session", "")
    return {
        "id": metadata.get("id", "unknown"),
        "task_name": metadata.get("task_name", task_dir.name),
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
        "path": str(task_dir.resolve()),
    }


def discover(
    workspace: Path,
    execution_root: Path | None,
    statuses: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    workspace = workspace.expanduser().resolve()
    workspace_file = workspace / "workspace.yaml"
    if not workspace_file.is_file():
        raise ValueError(f"not an initialized agent workspace: {workspace}")
    title, workspace_id = workspace_identity(workspace_file)
    candidates = indexed_paths(workspace)
    if execution_root is not None and execution_root.is_dir():
        candidates.extend(path for path in execution_root.iterdir() if path.is_dir())

    tasks: list[dict[str, str]] = []
    missing_paths: list[str] = []
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.expanduser()
        if not candidate.exists():
            missing_paths.append(str(candidate))
            continue
        resolved = candidate.resolve()
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        task = task_from_path(resolved, workspace, title, workspace_id)
        if task is not None and (statuses is None or task["status"] in statuses):
            tasks.append(task)
    tasks.sort(
        key=lambda task: (
            STATUS_ORDER.get(task["status"], STATUS_ORDER["unknown"]),
            task["task_name"].casefold(),
        )
    )
    return tasks, sorted(set(missing_paths))


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(tasks: list[dict[str, str]], missing_paths: list[str]) -> str:
    if not tasks:
        output = "No workspace tasks found."
    else:
        lines = [
            "| Status | Task | Updated | Recorded TSS target | Path |",
            "| --- | --- | --- | --- | --- |",
        ]
        for task in tasks:
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(task[key])
                    for key in ("status", "task_name", "updated", "tss_target", "path")
                )
                + " |"
            )
        output = "\n".join(lines)
    if missing_paths:
        output += "\n\nMissing recorded execution folders:\n"
        output += "\n".join(f"- `{path}`" for path in missing_paths)
    return output


def render_json(
    workspace: Path,
    execution_root: Path | None,
    tasks: list[dict[str, str]],
    missing_paths: list[str],
) -> str:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "execution_root": str(execution_root) if execution_root is not None else "",
        "tasks": tasks,
        "missing_paths": missing_paths,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path)
    parser.add_argument("--execution-root", type=Path)
    parser.add_argument(
        "--status",
        action="append",
        choices=tuple(STATUS_ORDER),
        help="include only this task status; repeat to include several",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    arguments = parser.parse_args()
    try:
        workspace = arguments.workspace.expanduser().resolve()
        root = arguments.execution_root
        if root is not None:
            root = root.expanduser()
            if not root.is_absolute():
                raise ValueError(f"execution root must be absolute: {root}")
            root = root.resolve()
        else:
            root = configured_execution_root(arguments.config)
        statuses = set(arguments.status) if arguments.status else None
        tasks, missing_paths = discover(workspace, root, statuses)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(render_json(workspace, root, tasks, missing_paths))
    else:
        print(render_markdown(tasks, missing_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
