#!/usr/bin/env python3
"""Maintain portable workspace task history stored at the workspace root."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HISTORY_FILE = "task-history.json"
SCHEMA_VERSION = 1


def history_path(workspace: Path) -> Path:
    return workspace.expanduser().resolve() / HISTORY_FILE


def load_history(workspace: Path) -> dict[str, Any]:
    path = history_path(workspace)
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "hosts": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read workspace task history {path}: {exc}") from exc
    hosts = payload.get("hosts") if isinstance(payload, dict) else None
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(hosts, dict):
        raise ValueError(f"workspace task history has an invalid format: {path}")
    return payload


def save_history(workspace: Path, payload: dict[str, Any]) -> None:
    path = history_path(workspace)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="task-history.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def record_task_use(
    workspace: Path,
    *,
    host: str,
    task_id: str,
    task_name: str,
    status: str,
    execution_folder: Path,
    tss_target: str = "",
    used_at: str | None = None,
) -> dict[str, str]:
    """Store one task under its current host and its own most-recent-use time."""
    if not host:
        raise ValueError("workspace task history needs a host")
    if not task_id or not task_name:
        raise ValueError("workspace task history needs a task id and task name")
    payload = load_history(workspace)
    hosts = payload["hosts"]
    for host_payload in hosts.values():
        if not isinstance(host_payload, dict):
            continue
        tasks = host_payload.get("tasks")
        if not isinstance(tasks, dict):
            continue
        for name, record in list(tasks.items()):
            if isinstance(record, dict) and record.get("id") == task_id:
                del tasks[name]
    host_payload = hosts.setdefault(host, {"tasks": {}})
    if not isinstance(host_payload, dict):
        raise ValueError(f"workspace task history host entry is invalid: {host}")
    tasks = host_payload.setdefault("tasks", {})
    if not isinstance(tasks, dict):
        raise ValueError(f"workspace task history task map is invalid: {host}")
    timestamp = used_at or current_timestamp()
    tasks[task_name] = {
        "id": task_id,
        "last_used_at": timestamp,
        "status": status,
        "execution_folder": str(execution_folder.expanduser().resolve()),
        "tss_target": tss_target,
    }
    save_history(workspace, payload)
    return {"host": host, "last_used_at": timestamp, "task_name": task_name}


def history_tasks(workspace: Path) -> list[dict[str, str]]:
    payload = load_history(workspace)
    records: list[dict[str, str]] = []
    for host, host_payload in payload["hosts"].items():
        if not isinstance(host, str) or not isinstance(host_payload, dict):
            continue
        tasks = host_payload.get("tasks")
        if not isinstance(tasks, dict):
            continue
        for task_name, record in tasks.items():
            if not isinstance(task_name, str) or not isinstance(record, dict):
                continue
            task_id = record.get("id")
            last_used_at = record.get("last_used_at")
            if not isinstance(task_id, str) or not isinstance(last_used_at, str):
                continue
            records.append({
                "id": task_id, "task_name": task_name,
                "status": record.get("status", "unknown"), "host": host,
                "last_used_at": last_used_at, "tss_target": record.get("tss_target", ""),
                "path": record.get("execution_folder", ""), "history_only": "1",
            })
    return records
