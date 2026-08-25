#!/usr/bin/env python3
"""Create a workspace task and its tmux session on a remote SSH host."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Any


SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DEFAULT_SKILL_ROOT = '"$HOME/.agents/skills"'


def absolute_remote_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute remote path: {value}")
    return str(path)


def remote_script(skill_root: str, relative_path: str) -> str:
    if skill_root == DEFAULT_SKILL_ROOT:
        return f"{skill_root}/{relative_path}"
    return shlex.quote(str(PurePosixPath(skill_root) / relative_path))


def python_command(script: str, *arguments: str) -> str:
    return f"python3 {script} {shlex.join(arguments)}"


def run_ssh(ssh_command: str, host: str, remote_command: str) -> str:
    result = subprocess.run(
        [ssh_command, host, remote_command],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"remote command failed on {host}: {detail}")
    return result.stdout


def json_result(output: str, operation: str) -> dict[str, Any]:
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{operation} did not return JSON: {output.strip()}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{operation} returned a JSON value other than an object")
    return value


def start_remote_workspace_task(
    host: str,
    workspace: str,
    task_name: str,
    objective: str,
    session_name: str | None = None,
    execution_folder: str | None = None,
    remote_skill_root: str = DEFAULT_SKILL_ROOT,
    ssh_command: str = "ssh",
) -> dict[str, Any]:
    if not SAFE_HOST.fullmatch(host):
        raise ValueError("remote host may contain letters, digits, dots, underscores, and hyphens")
    workspace = absolute_remote_path(workspace, "workspace")
    if execution_folder is not None:
        execution_folder = absolute_remote_path(execution_folder, "execution folder")
    if remote_skill_root != DEFAULT_SKILL_ROOT:
        remote_skill_root = absolute_remote_path(remote_skill_root, "remote skill root")

    initializer = remote_script(
        remote_skill_root, "agent-workspace/scripts/start_workspace_task.py"
    )
    session_helper = remote_script(
        remote_skill_root, "task-session/scripts/start_task_session.py"
    )
    preflight = (
        f"command -v python3 >/dev/null && command -v tmux >/dev/null "
        f"&& test -f {initializer} && test -f {session_helper}"
    )
    run_ssh(ssh_command, host, preflight)

    initialize = [
        "--workspace",
        workspace,
        "--name",
        task_name,
        "--objective",
        objective,
        "--format",
        "json",
    ]
    if execution_folder is not None:
        initialize.extend(["--execution-folder", execution_folder])
    task = json_result(
        run_ssh(ssh_command, host, python_command(initializer, *initialize)),
        "remote task initialization",
    )
    task_dir = task.get("execution_folder")
    if not isinstance(task_dir, str):
        raise ValueError("remote task initialization returned no execution_folder")

    start_session = [
        "--task-dir",
        task_dir,
        "--workspace",
        workspace,
        "--tss-host",
        host,
        "--format",
        "json",
    ]
    if session_name is not None:
        start_session.extend(["--session-name", session_name])
    session = json_result(
        run_ssh(ssh_command, host, python_command(session_helper, *start_session)),
        "remote task session start",
    )
    target = session.get("tss_target")
    if not isinstance(target, str):
        raise ValueError("remote task session start returned no tss_target")
    return {"task": task, "session": session, "tss_target": target}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SSH and TSS host label")
    parser.add_argument("--workspace", required=True, help="absolute workspace path on the remote host")
    parser.add_argument("--name", required=True)
    parser.add_argument("--objective")
    parser.add_argument("--session-name")
    parser.add_argument("--execution-folder", help="absolute execution folder path on the remote host")
    parser.add_argument("--remote-skill-root", default=DEFAULT_SKILL_ROOT)
    parser.add_argument("--ssh-command", default="ssh", help=argparse.SUPPRESS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    arguments = parser.parse_args()
    try:
        result = start_remote_workspace_task(
            host=arguments.host,
            workspace=arguments.workspace,
            task_name=arguments.name,
            objective=arguments.objective or f"Complete {arguments.name}.",
            session_name=arguments.session_name,
            execution_folder=arguments.execution_folder,
            remote_skill_root=arguments.remote_skill_root,
            ssh_command=arguments.ssh_command,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Remote workspace task initialized.")
        print(f"Execution folder: {result['task']['execution_folder']}")
        print(f"Connect: tss {result['tss_target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
