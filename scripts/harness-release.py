#!/usr/bin/env python3
"""Create, register, inspect, and restore harness releases."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PAYLOAD = (
    "home",
    "instances",
    "claude",
    "agent-skills",
    "agent-workflows",
    "scripts/render-agents.py",
    "scripts/render-claude-settings.py",
    "scripts/render-codex-config.py",
    "scripts/harness-release.py",
    "install.sh",
    "update.sh",
    "README.md",
)


def payload_files(source: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for relative in PAYLOAD:
        path = source / relative
        if path.is_dir():
            files.extend(
                (str(child.relative_to(source)), child)
                for child in sorted(path.rglob("*"))
                if child.is_file()
            )
        elif path.is_file():
            files.append((relative, path))
        else:
            raise FileNotFoundError(f"release payload is missing {path}")
    return sorted(files)


def content_id(source: Path) -> str:
    digest = hashlib.sha256()
    for relative, path in payload_files(source):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{path.stat().st_mode & 0o777:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def stage_release(source: Path, destination: Path) -> str:
    source = source.resolve()
    release_id = content_id(source)
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "source").mkdir(parents=True)
    for relative in PAYLOAD:
        src = source / relative
        dst = destination / "source" / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    metadata = {
        "version": 1,
        "release_id": release_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (destination / "release.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return release_id


def read_release_id(release: Path) -> str:
    metadata = json.loads((release / "release.json").read_text(encoding="utf-8"))
    release_id = metadata.get("release_id")
    if not isinstance(release_id, str) or not re.fullmatch(
        r"[0-9a-f]{16}",
        release_id,
    ):
        raise ValueError(f"invalid release metadata in {release}")
    return release_id


def switch_current(home: Path, release_id: str) -> None:
    current = home / "current"
    temporary = home / f".current.tmp.{os.getpid()}"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(Path("releases") / release_id)
    os.replace(temporary, current)


def register_release(staged: Path, home: Path) -> str:
    release_id = read_release_id(staged)
    releases = home / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    target = releases / release_id
    if not target.exists():
        temporary = releases / f".{release_id}.tmp.{os.getpid()}"
        shutil.rmtree(temporary, ignore_errors=True)
        shutil.copytree(staged, temporary)
        os.replace(temporary, target)
    switch_current(home, release_id)
    return release_id


def current_release(home: Path) -> str | None:
    current = home / "current"
    if not current.is_symlink():
        return None
    return Path(os.readlink(current)).name


def list_releases(home: Path) -> list[tuple[str, str]]:
    releases = home / "releases"
    result: list[tuple[str, str]] = []
    if not releases.is_dir():
        return result
    for path in sorted(releases.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        try:
            metadata = json.loads(
                (path / "release.json").read_text(encoding="utf-8")
            )
            result.append((path.name, str(metadata.get("created_at", "unknown"))))
        except (OSError, ValueError, json.JSONDecodeError):
            result.append((path.name, "invalid metadata"))
    return result


def rollback(home: Path, release_id: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{16}", release_id):
        raise ValueError(f"invalid release ID: {release_id}")
    release = home / "releases" / release_id
    installer = release / "source/install.sh"
    if not installer.is_file():
        raise FileNotFoundError(f"release does not exist: {release_id}")
    env = os.environ.copy()
    env["AGENT_HARNESS_HOME"] = str(home)
    subprocess.run(
        [str(installer), "--update", "--no-release"],
        cwd=release / "source",
        env=env,
        check=True,
    )
    switch_current(home, release_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home",
        type=Path,
        default=Path(
            os.environ.get(
                "AGENT_HARNESS_HOME",
                Path.home() / ".agent-harness",
            )
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--destination", type=Path, required=True)

    register = commands.add_parser("register")
    register.add_argument("--staged", type=Path, required=True)

    commands.add_parser("list")
    commands.add_parser("current")

    restore = commands.add_parser("rollback")
    restore.add_argument("release_id")

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(stage_release(args.source, args.destination))
        elif args.command == "register":
            print(register_release(args.staged, args.home))
        elif args.command == "list":
            active = current_release(args.home)
            for release_id, created_at in list_releases(args.home):
                marker = "*" if release_id == active else " "
                print(f"{marker} {release_id}  {created_at}")
        elif args.command == "current":
            active = current_release(args.home)
            if active is None:
                raise FileNotFoundError("no active harness release")
            print(active)
        else:
            rollback(args.home, args.release_id)
            print(f"restored harness release {args.release_id}")
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
