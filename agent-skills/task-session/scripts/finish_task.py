#!/usr/bin/env python3
"""Complete a task record and mark its tmux session for later TSS cleanup."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from set_task_state import TERMINAL_STATUSES, set_task_state


def finish_task(
    task_dir: Path,
    outcome: str,
    status: str = "done",
    socket_name: str | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"unsupported terminal task status: {status}")
    return set_task_state(
        task_dir,
        status,
        outcome,
        socket_name=socket_name,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--status", choices=sorted(TERMINAL_STATUSES), default="done")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--tmux-socket", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    try:
        result = finish_task(
            arguments.task_dir,
            arguments.outcome,
            status=arguments.status,
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
            print(f"Session marked for later cleanup: {result['session_name']}")
        else:
            print(f"Session cleanup marker not written: {result['session_warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
