#!/usr/bin/env python3
"""Create one agent-task workspace from the bundled template."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

from catalog_client import CatalogError, run_catalog_json


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
    parser.add_argument(
        "--catalog-cli",
        type=Path,
        help="task-catalog executable (defaults to the installed harness command)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        target = hydrate(args.name, args.objective, args.destination)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    registration_error = ""
    try:
        run_catalog_json(
            ("register", "--path", str(target), "--format", "json"),
            executable=args.catalog_cli,
        )
    except CatalogError as exc:
        registration_error = str(exc)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "operation": "hydrate-agent-task",
                    "path": str(target),
                    "catalog_registered": not registration_error,
                    "registration_error": registration_error,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(target)
    if registration_error:
        print(
            "warning: task folder was created but catalog registration failed: "
            f"{registration_error}",
            file=sys.stderr,
        )
        print(
            f"recovery: task-catalog register --path {target!s}",
            file=sys.stderr,
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
