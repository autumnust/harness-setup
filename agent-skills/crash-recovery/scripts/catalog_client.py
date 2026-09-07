#!/usr/bin/env python3
"""Small subprocess client for the installed machine-local task catalog."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


def catalog_executable() -> Path:
    harness_home = Path(
        os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
    ).expanduser()
    return harness_home / "bin" / "task-catalog"


def list_records(*arguments: str) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            [str(catalog_executable()), "list", "--format", "json", *arguments],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise ValueError(f"task catalog query could not run: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise ValueError(f"task catalog query failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("task catalog returned invalid JSON") from exc
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError("task catalog JSON has no records list")
    return records
