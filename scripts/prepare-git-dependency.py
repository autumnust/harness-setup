#!/usr/bin/env python3
"""Clone one lockfile-pinned Git dependency into an empty staging directory."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FIELDS = {"name", "repository", "revision", "entrypoint"}


def load_manifest(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read dependency manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != REQUIRED_FIELDS:
        raise ValueError(
            f"dependency manifest must contain exactly: {', '.join(sorted(REQUIRED_FIELDS))}"
        )
    if not all(isinstance(value[key], str) and value[key] for key in REQUIRED_FIELDS):
        raise ValueError("dependency manifest values must be non-empty strings")
    if not re.fullmatch(r"[0-9a-f]{40}", value["revision"]):
        raise ValueError("dependency revision must be a 40-character lowercase Git commit ID")
    if "/" in value["entrypoint"] or "\\" in value["entrypoint"]:
        raise ValueError("dependency entrypoint must be one filename")
    return value


def prepare(manifest_path: Path, destination: Path) -> dict[str, str]:
    manifest = load_manifest(manifest_path)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"staging destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--quiet", manifest["repository"], str(destination)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", manifest["revision"]],
        check=True,
    )
    entrypoint = destination / manifest["entrypoint"]
    if not entrypoint.is_file():
        raise ValueError(
            f"dependency {manifest['name']} revision {manifest['revision']} has no {manifest['entrypoint']}"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        manifest = prepare(arguments.manifest, arguments.destination)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Prepared {manifest['name']} at {arguments.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
