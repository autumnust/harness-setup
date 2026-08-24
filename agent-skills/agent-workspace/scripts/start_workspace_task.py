#!/usr/bin/env python3
"""Create one execution folder for a task in an initialized agent workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Any


NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9._/@+-]+", value):
        return value
    return "'" + value.replace("'", "''") + "'"


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


def load_runtime_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        harness_home = Path(
            os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
        ).expanduser()
        path = harness_home / "config.json"
    if not path.is_file():
        raise ValueError(f"runtime configuration does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"runtime configuration must contain an object: {path}")
    return value


def absolute_path(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path: {path}")
    return path.resolve()


def resolve_execution_folder(
    task_name: str,
    config: dict[str, Any],
    execution_root: Path | None,
    execution_folder: Path | None,
) -> Path:
    if execution_folder is not None:
        target = absolute_path(execution_folder, "execution folder")
        if not target.parent.is_dir():
            raise ValueError(f"execution-folder parent does not exist: {target.parent}")
        return target
    root_value: str | Path | None = execution_root
    if root_value is None:
        configured = config.get("execution_root")
        root_value = configured if isinstance(configured, str) and configured else None
    if root_value is None:
        raise ValueError(
            "execution root is unresolved; pass --execution-root or configure execution_root"
        )
    root = absolute_path(root_value, "execution root")
    if not root.is_dir():
        raise ValueError(f"execution root does not exist or is not a directory: {root}")
    return root / task_name


def relative_link(source_dir: Path, target: Path) -> str:
    return os.path.relpath(target, start=source_dir)


def task_readme(
    task_id: str,
    task_name: str,
    objective: str,
    workspace: Path,
    workspace_title: str,
    workspace_id: str,
    task_dir: Path,
) -> str:
    today = date.today().isoformat()
    workspace_href = relative_link(task_dir, workspace)
    return f"""---
workspace_task: 1
id: {yaml_scalar(task_id)}
task_name: {yaml_scalar(task_name)}
title: {yaml_scalar(task_name)}
status: active
workspace: {yaml_scalar(workspace_title)}
workspace_id: {yaml_scalar(workspace_id)}
workspace_path: {yaml_scalar(str(workspace))}
created: {today}
updated: {today}
---

# {task_name}

## Goal

{objective}

## Workspace

This execution belongs to [{workspace_title}]({workspace_href}). Repository
changes follow that workspace's instructions and are created only when the work
requires them.

## Current state

The task record is initialized and ready for work. If the coordinator selects
the full workflow, it creates the additional execution structure before work
begins.

## Immediate next task

1. Connect to the recorded tmux session.
2. Confirm the first concrete work item and begin execution.

## Resume

Read this file, then continue from the immediate next task. The tmux host and
session are recorded in the front matter after session creation.
"""


def task_index_path(workspace: Path) -> Path:
    git_dir = workspace / ".git"
    if not git_dir.is_dir():
        raise ValueError(f"workspace root is not a Git repository: {workspace}")
    return git_dir / "agent-workspace" / "task-paths.json"


def load_task_paths(index_path: Path) -> list[str]:
    if not index_path.is_file():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read workspace task index {index_path}: {exc}") from exc
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(f"workspace task index has an invalid paths list: {index_path}")
    return paths


def save_task_path(index_path: Path, task_dir: Path) -> None:
    paths = load_task_paths(index_path)
    task_value = str(task_dir)
    if task_value not in paths:
        paths.append(task_value)
    payload = {"schema_version": 1, "paths": sorted(paths)}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="task-paths.", suffix=".tmp", dir=index_path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary_name, index_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def initialize_task(
    workspace: Path,
    task_name: str,
    objective: str,
    config_path: Path | None = None,
    execution_root: Path | None = None,
    execution_folder: Path | None = None,
) -> dict[str, str]:
    workspace = workspace.expanduser().resolve()
    if not NAME_PATTERN.fullmatch(task_name):
        raise ValueError(
            "task name may contain letters, digits, dots, underscores, and hyphens"
        )
    workspace_file = workspace / "workspace.yaml"
    if not workspace_file.is_file():
        raise ValueError(f"not an initialized agent workspace: {workspace}")
    title, workspace_id = workspace_identity(workspace_file)
    config = load_runtime_config(config_path)
    task_dir = resolve_execution_folder(
        task_name, config, execution_root, execution_folder
    )
    if task_dir.exists() or task_dir.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing execution path: {task_dir}")

    task_id = str(uuid.uuid4())
    created_task = False
    try:
        task_dir.mkdir()
        created_task = True
        (task_dir / "README.md").write_text(
            task_readme(
                task_id,
                task_name,
                objective,
                workspace,
                title,
                workspace_id,
                task_dir,
            ),
            encoding="utf-8",
        )
        save_task_path(task_index_path(workspace), task_dir)
    except Exception:
        if created_task:
            shutil.rmtree(task_dir)
        raise

    return {
        "execution_folder": str(task_dir),
        "task_id": task_id,
        "task_name": task_name,
        "workspace": str(workspace),
        "workspace_id": workspace_id,
        "workspace_name": title,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--objective")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path)
    parser.add_argument("--execution-root", type=Path)
    parser.add_argument("--execution-folder", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    arguments = parser.parse_args()
    try:
        result = initialize_task(
            workspace=arguments.workspace,
            task_name=arguments.name,
            objective=arguments.objective or f"Complete {arguments.name}.",
            config_path=arguments.config,
            execution_root=arguments.execution_root,
            execution_folder=arguments.execution_folder,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Workspace task initialized.")
        print(f"Execution folder: {result['execution_folder']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
