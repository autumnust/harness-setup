#!/usr/bin/env python3
"""Create one agent-task workspace from the bundled template."""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "workspace-template"


def valid_folder_name(value: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value:
        raise argparse.ArgumentTypeError("name must be one folder name, not a path")
    if any(ord(character) < 32 for character in value):
        raise argparse.ArgumentTypeError("name must not contain control characters")
    return value


def hydrate(name: str, objective: str, destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    if not destination.is_dir():
        raise ValueError(f"destination directory does not exist: {destination}")

    target = destination / name
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing path: {target}")

    shutil.copytree(TEMPLATE, target)
    readme = target / "README.md"
    today = date.today().isoformat()
    replacements = {
        "[AGENT_TASK_VERSION]": "1",
        "[TASK_ID]": str(uuid.uuid4()),
        "[TASK_NAME]": name,
        "[OBJECTIVE]": objective,
        "[DATE]": today,
    }
    content = readme.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    readme.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, type=valid_folder_name)
    parser.add_argument("--objective", default="Define the objective.")
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        target = hydrate(args.name, args.objective, args.destination)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
