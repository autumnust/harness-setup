#!/usr/bin/env python3
"""Start a tmux session for an existing task and print its TSS target."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_front_matter(text: str) -> tuple[dict[str, str], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("task README needs YAML front matter")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("task README has unterminated YAML front matter") from exc
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = yaml_unquote(value.strip())
    return metadata, end


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


def update_front_matter(readme: Path, updates: dict[str, str]) -> None:
    text = readme.read_text(encoding="utf-8")
    _metadata, end = parse_front_matter(text)
    lines = text.splitlines()
    pending = dict(updates)
    for index in range(1, end):
        if ":" not in lines[index]:
            continue
        key = lines[index].split(":", 1)[0].strip()
        if key in pending:
            lines[index] = f"{key}: {yaml_scalar(pending.pop(key))}"
    additions = [f"{key}: {yaml_scalar(value)}" for key, value in pending.items()]
    lines[end:end] = additions
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_workspace_reference(
    readme: Path,
    task_dir: Path,
    workspace: Path,
    workspace_name: str,
) -> None:
    text = readme.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading = "## Workspace"
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == heading),
        None,
    )
    if start is None:
        return
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    href = os.path.relpath(workspace, start=task_dir)
    replacement = [
        heading,
        "",
        f"This execution belongs to [{workspace_name}]({href}). Repository",
        "changes follow that workspace's instructions and are created only when the work",
        "requires them.",
        "",
    ]
    lines[start:end] = replacement
    readme.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_runtime_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        harness_home = Path(
            os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
        ).expanduser()
        path = harness_home / "config.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"runtime configuration must contain an object: {path}")
    return value


def configured_tss_host(config: dict[str, Any]) -> str | None:
    task_runtime = config.get("task_runtime")
    if not isinstance(task_runtime, dict):
        return None
    tss = task_runtime.get("tss")
    if not isinstance(tss, dict):
        return None
    host = tss.get("host_alias")
    return host if isinstance(host, str) and host else None


def normalized_session_name(task_name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", task_name.strip()).strip("-.")
    if not value:
        raise ValueError("task name cannot produce a valid tmux session name")
    return value


def infer_task_kind(metadata: dict[str, str]) -> str:
    if metadata.get("workspace_task") == "1":
        return "workspace-task"
    if metadata.get("agent_task") == "1":
        return "agent-task"
    raise ValueError("task README is not an agent-task or workspace task record")


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


def resolve_working_directory(
    task_dir: Path,
    metadata: dict[str, str],
    workspace: Path | None,
) -> Path:
    if infer_task_kind(metadata) == "agent-task":
        if workspace is not None:
            raise ValueError("--workspace is only valid for a workspace task")
        return task_dir

    candidate_value: str | Path | None = workspace
    if candidate_value is None:
        candidate_value = metadata.get("workspace_path") or None
    if candidate_value is None:
        raise ValueError(
            "workspace path is unresolved; pass --workspace with this host's workspace path"
        )
    candidate = Path(candidate_value).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"workspace path must be absolute: {candidate}")
    candidate = candidate.resolve()
    manifest = candidate / "workspace.yaml"
    if not manifest.is_file():
        source = "provided" if workspace is not None else "recorded"
        raise ValueError(
            f"{source} workspace path has no workspace.yaml: {candidate}; "
            "pass --workspace with this host's workspace path"
        )
    name, workspace_id = workspace_identity(manifest)
    recorded_id = metadata.get("workspace_id", "")
    if recorded_id and workspace_id and recorded_id != workspace_id:
        raise ValueError("workspace id does not match the task record")
    if not (recorded_id and workspace_id) and metadata.get("workspace") != name:
        raise ValueError("workspace name does not match the task record")
    return candidate


def tmux_command(socket_name: str | None, *arguments: str) -> list[str]:
    command = ["tmux"]
    if socket_name:
        command.extend(["-L", socket_name])
    command.extend(arguments)
    return command


def run_tmux(
    socket_name: str | None,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        tmux_command(socket_name, *arguments),
        check=check,
        text=True,
        capture_output=True,
    )


def existing_task_id(socket_name: str | None, session_name: str) -> str | None:
    result = run_tmux(
        socket_name,
        "show-options",
        "-v",
        "-t",
        session_name,
        "@agent_task_id",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def session_exists(socket_name: str | None, session_name: str) -> bool:
    result = run_tmux(
        socket_name, "list-sessions", "-F", "#{session_name}", check=False
    )
    if result.returncode != 0:
        return False
    return session_name in result.stdout.splitlines()


def start_session(
    task_dir: Path,
    tss_host: str,
    session_name: str,
    workspace: Path | None = None,
    socket_name: str | None = None,
) -> dict[str, Any]:
    task_dir = task_dir.expanduser().resolve()
    if not task_dir.is_dir():
        raise ValueError(f"task directory does not exist: {task_dir}")
    readme = task_dir / "README.md"
    if not readme.is_file():
        raise ValueError(f"task directory has no README.md: {task_dir}")
    metadata, _end = parse_front_matter(readme.read_text(encoding="utf-8"))
    task_id = metadata.get("id")
    if not task_id:
        raise ValueError("task README front matter needs a stable id")
    task_name = metadata.get("task_name") or metadata.get("title") or task_dir.name
    task_kind = infer_task_kind(metadata)
    working_directory = resolve_working_directory(task_dir, metadata, workspace)

    if not SAFE_NAME.fullmatch(tss_host):
        raise ValueError("TSS host label may contain letters, digits, dots, underscores, and hyphens")
    if not SAFE_NAME.fullmatch(session_name):
        raise ValueError("tmux session name may contain letters, digits, dots, underscores, and hyphens")
    if shutil.which("tmux") is None:
        raise ValueError("tmux is not installed or not available on PATH")

    created = False
    if session_exists(socket_name, session_name):
        owner = existing_task_id(socket_name, session_name)
        if owner != task_id:
            raise ValueError(
                f"tmux session already belongs to another or unrecorded task: {session_name}"
            )
    else:
        run_tmux(
            socket_name,
            "new-session",
            "-d",
            "-s",
            session_name,
            "-c",
            str(working_directory),
        )
        created = True
    options = {
        "@agent_task_id": task_id,
        "@agent_task_name": task_name,
        "@agent_task_kind": task_kind,
        "@agent_task_path": str(task_dir),
        "@agent_task_status": metadata.get("status", "active"),
        "@agent_tss_host": tss_host,
    }
    if metadata.get("workspace"):
        options["@agent_workspace"] = metadata["workspace"]
    if task_kind == "workspace-task":
        options["@agent_workspace_path"] = str(working_directory)
    if metadata.get("state_changed_at"):
        options["@agent_task_state_changed_at"] = metadata["state_changed_at"]
    if metadata.get("completed"):
        options["@agent_task_finished_at"] = metadata["completed"]
    try:
        for key, value in options.items():
            run_tmux(
                socket_name,
                "set-option",
                "-t",
                session_name,
                key,
                value,
            )
    except (OSError, subprocess.CalledProcessError):
        if created:
            run_tmux(
                socket_name, "kill-session", "-t", session_name, check=False
            )
        raise

    try:
        updates = {
            "runtime_host": tss_host,
            "tmux_session": session_name,
            "updated": date.today().isoformat(),
        }
        if task_kind == "workspace-task":
            updates["workspace_path"] = str(working_directory)
        update_front_matter(readme, updates)
        if task_kind == "workspace-task":
            update_workspace_reference(
                readme,
                task_dir,
                working_directory,
                metadata.get("workspace", working_directory.name),
            )
    except OSError:
        if created:
            run_tmux(
                socket_name, "kill-session", "-t", session_name, check=False
            )
        raise
    return {
        "created": created,
        "session_name": session_name,
        "task_dir": str(task_dir),
        "task_id": task_id,
        "task_kind": task_kind,
        "tss_host": tss_host,
        "tss_target": f"{tss_host}:{session_name}",
        "working_directory": str(working_directory),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--tss-host")
    parser.add_argument("--session-name")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="current host path for a workspace task",
    )
    parser.add_argument("--config", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--tmux-socket", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    try:
        task_dir = arguments.task_dir.expanduser().resolve()
        readme = task_dir / "README.md"
        if not readme.is_file():
            raise ValueError(f"task directory has no README.md: {task_dir}")
        metadata, _end = parse_front_matter(readme.read_text(encoding="utf-8"))
        task_name = metadata.get("task_name") or metadata.get("title") or task_dir.name
        config = load_runtime_config(arguments.config)
        tss_host = arguments.tss_host or configured_tss_host(config)
        if not tss_host:
            raise ValueError(
                "TSS host label is unresolved; pass --tss-host or configure "
                "task_runtime.tss.host_alias"
            )
        session_name = arguments.session_name or normalized_session_name(task_name)
        result = start_session(
            task_dir,
            tss_host,
            session_name,
            workspace=arguments.workspace,
            socket_name=arguments.tmux_socket,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"error: tmux command failed: {detail}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        state = "created" if result["created"] else "already active"
        print(f"Task session {state}.")
        print(f"Working directory: {result['working_directory']}")
        print(f"Execution folder: {result['task_dir']}")
        print(f"Connect: tss {result['tss_target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
