#!/usr/bin/env python3
"""Small subprocess client for the installed task-catalog command."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


class CatalogError(RuntimeError):
    """The catalog command could not complete the requested operation."""


def catalog_executable(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    harness_home = Path(
        os.environ.get("AGENT_HARNESS_HOME", str(Path.home() / ".agent-harness"))
    )
    return harness_home.expanduser().resolve() / "bin" / "task-catalog"


def run_catalog_json(
    arguments: Sequence[str], *, executable: Path | None = None
) -> dict[str, Any]:
    command = catalog_executable(executable)
    try:
        result = subprocess.run(
            [str(command), *arguments],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError as exc:
        raise CatalogError(f"cannot run task catalog at {command}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no error detail"
        raise CatalogError(
            f"task catalog command failed with exit code {result.returncode}: {detail}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CatalogError(f"task catalog returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CatalogError("task catalog JSON must be an object")
    return payload
