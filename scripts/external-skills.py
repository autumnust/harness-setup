#!/usr/bin/env python3
"""Resolve and refresh commit-pinned external agent skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse


MANIFEST_FIELDS = {"schema_version", "skills"}
SKILL_FIELDS = {
    "name",
    "repository",
    "tracking_ref",
    "revision",
    "source_path",
    "license_path",
    "content_sha256",
}
NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")
REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
LICENSE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    "COPYING.md",
    "COPYING.txt",
)


def _run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, **kwargs)


def _safe_relative_path(
    value: object, field: str, allow_repository_root: bool = False
) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if allow_repository_root and value == ".":
        return value
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != value
    ):
        raise ValueError(f"{field} must be a normalized relative path")
    return value


def validate_manifest(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != MANIFEST_FIELDS:
        raise ValueError(
            "external skill manifest must contain exactly schema_version and skills"
        )
    if value["schema_version"] != 1:
        raise ValueError("external skill manifest schema_version must be 1")
    skills = value["skills"]
    if not isinstance(skills, list):
        raise ValueError("external skill manifest skills must be a list")

    names: set[str] = set()
    for index, skill in enumerate(skills):
        prefix = f"skills[{index}]"
        if not isinstance(skill, dict) or set(skill) != SKILL_FIELDS:
            raise ValueError(
                f"{prefix} must contain exactly: {', '.join(sorted(SKILL_FIELDS))}"
            )
        name = skill["name"]
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise ValueError(f"{prefix}.name must use lowercase letters, numbers, and hyphens")
        if name in names:
            raise ValueError(f"external skill name appears more than once: {name}")
        names.add(name)
        for field in ("repository", "tracking_ref"):
            if not isinstance(skill[field], str) or not skill[field]:
                raise ValueError(f"{prefix}.{field} must be a non-empty string")
        if not REVISION_PATTERN.fullmatch(str(skill["revision"])):
            raise ValueError(f"{prefix}.revision must be a 40-character Git commit ID")
        if not HASH_PATTERN.fullmatch(str(skill["content_sha256"])):
            raise ValueError(f"{prefix}.content_sha256 must be a SHA-256 hash")
        _safe_relative_path(
            skill["source_path"],
            f"{prefix}.source_path",
            allow_repository_root=True,
        )
        _safe_relative_path(skill["license_path"], f"{prefix}.license_path")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read external skill manifest {path}: {exc}") from exc
    return validate_manifest(value)


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    validate_manifest(manifest)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def tree_hash(directory: Path) -> str:
    if not directory.is_dir():
        raise ValueError(f"skill directory does not exist: {directory}")
    digest = hashlib.sha256()
    entries = sorted(directory.rglob("*"))
    for path in entries:
        if path.is_symlink():
            raise ValueError(f"external skills may not contain symbolic links: {path}")
    files = [path for path in entries if path.is_file()]
    if not files:
        raise ValueError(f"skill directory contains no files: {directory}")
    for path in files:
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{path.stat().st_mode & 0o777:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _checkout_paths(
    repository: str,
    revision: str,
    tracking_ref: str,
    paths: list[tuple[str, bool]],
    destination: Path,
) -> None:
    sparse_paths = [
        "/*"
        if path == "." and is_directory
        else f"/{path}/"
        if is_directory
        else f"/{path}"
        for path, is_directory in paths
    ]
    destination.mkdir(parents=True)
    _run(["git", "-C", str(destination), "init", "--quiet"])
    _run(
        [
            "git",
            "-C",
            str(destination),
            "remote",
            "add",
            "origin",
            repository,
        ]
    )
    _run(
        [
            "git",
            "-C",
            str(destination),
            "sparse-checkout",
            "set",
            "--no-cone",
            *sparse_paths,
        ]
    )
    fetch = subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--quiet",
            "--depth",
            "1",
            "--filter=blob:none",
            "origin",
            revision,
        ],
        text=True,
        capture_output=True,
    )
    if fetch.returncode != 0:
        _run(
            [
                "git",
                "-C",
                str(destination),
                "fetch",
                "--quiet",
                "--filter=blob:none",
                "origin",
                tracking_ref,
            ]
        )
    _run(
        [
            "git",
            "-C",
            str(destination),
            "checkout",
            "--quiet",
            "--detach",
            revision,
        ]
    )


def _checkout(skill: dict[str, str], destination: Path) -> None:
    _checkout_paths(
        skill["repository"],
        skill["revision"],
        skill["tracking_ref"],
        [(skill["source_path"], True), (skill["license_path"], False)],
        destination,
    )


def _read_skill_name(skill_directory: Path) -> str:
    skill_file = skill_directory / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"external skill directory has no SKILL.md: {skill_directory}")
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        raise ValueError(f"external skill has invalid front matter: {skill_file}")
    name_match = re.search(r"^name:\s*([^\s]+)\s*$", match.group(1), re.MULTILINE)
    if not name_match:
        raise ValueError(f"external skill front matter has no name: {skill_file}")
    return name_match.group(1)


def _validate_skill_name(skill_directory: Path, expected_name: str) -> None:
    actual = _read_skill_name(skill_directory)
    if actual != expected_name:
        raise ValueError(
            f"external skill directory is named {expected_name}, but SKILL.md names {actual}"
        )


def _copy_skill(checkout: Path, skill: dict[str, str], destination: Path) -> str:
    source = checkout / skill["source_path"]
    license_source = checkout / skill["license_path"]
    if not source.is_dir():
        raise ValueError(
            f"external skill {skill['name']} has no directory {skill['source_path']}"
        )
    if not license_source.is_file():
        raise ValueError(
            f"external skill {skill['name']} has no license {skill['license_path']}"
        )
    source_paths = [
        path
        for path in source.rglob("*")
        if ".git" not in path.relative_to(source).parts
    ]
    for path in [source, *source_paths, license_source]:
        if path.is_symlink():
            raise ValueError(f"external skills may not contain symbolic links: {path}")
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git"))
    upstream_license = destination / "LICENSE.upstream"
    if upstream_license.exists():
        raise ValueError(
            f"external skill {skill['name']} already contains LICENSE.upstream"
        )
    shutil.copy2(license_source, upstream_license)
    _validate_skill_name(destination, skill["name"])
    return tree_hash(destination)


def materialize_skill(
    skill: dict[str, str], destination: Path, verify_hash: bool = True
) -> str:
    with tempfile.TemporaryDirectory(prefix="external-skill-checkout.") as temp:
        checkout = Path(temp) / "repository"
        _checkout(skill, checkout)
        calculated = _copy_skill(checkout, skill, destination)
    if verify_hash and calculated != skill["content_sha256"]:
        raise ValueError(
            f"external skill {skill['name']} hash mismatch: "
            f"expected {skill['content_sha256']}, got {calculated}"
        )
    return calculated


def materialize_manifest(manifest_path: Path, destination: Path) -> None:
    manifest = load_manifest(manifest_path)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"external skill destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="external-skills.", dir=destination.parent
    ) as temp:
        staged = Path(temp) / "resolved"
        staged.mkdir()
        for skill in manifest["skills"]:
            materialize_skill(skill, staged / skill["name"])
        os.replace(staged, destination)


def verify_resolved(manifest_path: Path, directory: Path) -> None:
    manifest = load_manifest(manifest_path)
    if not directory.is_dir():
        raise ValueError(f"resolved external skill directory does not exist: {directory}")
    expected = {skill["name"] for skill in manifest["skills"]}
    actual = {path.name for path in directory.iterdir() if path.is_dir()}
    extra_files = [path.name for path in directory.iterdir() if not path.is_dir()]
    if actual != expected or extra_files:
        raise ValueError(
            "resolved external skill names do not match the manifest: "
            f"expected {sorted(expected)}, got directories {sorted(actual)} "
            f"and files {sorted(extra_files)}"
        )
    for skill in manifest["skills"]:
        skill_directory = directory / skill["name"]
        _validate_skill_name(skill_directory, skill["name"])
        calculated = tree_hash(skill_directory)
        if calculated != skill["content_sha256"]:
            raise ValueError(
                f"resolved external skill {skill['name']} hash mismatch: "
                f"expected {skill['content_sha256']}, got {calculated}"
            )


def _resolve_tracking_revision(repository: str, tracking_ref: str) -> str:
    result = _run(
        ["git", "ls-remote", repository, tracking_ref],
        capture_output=True,
    )
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or not REVISION_PATTERN.fullmatch(rows[0][0]):
        raise ValueError(f"could not resolve {tracking_ref} from {repository}")
    return rows[0][0]


def _github_base(repository: str) -> str | None:
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?", repository)
    if match:
        return f"https://github.com/{match.group(1)}"
    return None


def _remote_branches(repository: str) -> list[tuple[str, str]]:
    result = _run(
        ["git", "ls-remote", "--heads", repository],
        capture_output=True,
    )
    branches: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or not fields[1].startswith("refs/heads/"):
            continue
        branches.append((fields[1].removeprefix("refs/heads/"), fields[1]))
    return branches


def _parse_github_skill_url(
    url: str,
    repository_override: str | None = None,
) -> tuple[str, str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "github.com":
        raise ValueError("add-url currently accepts github.com skill links")
    parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
    if len(parts) < 4 or parts[2] not in {"blob", "tree"}:
        raise ValueError(
            "GitHub skill URL must use /OWNER/REPOSITORY/blob/BRANCH/.../SKILL.md "
            "or /OWNER/REPOSITORY/tree/BRANCH/..."
        )
    owner, repository_name, view = parts[:3]
    if not owner or not repository_name:
        raise ValueError("GitHub skill URL must identify an owner and repository")
    repository = repository_override or f"https://github.com/{owner}/{repository_name}.git"
    remainder = parts[3:]
    if any(not part for part in remainder):
        raise ValueError("GitHub skill URL path must not contain empty segments")
    matches: list[tuple[int, str, str, list[str]]] = []
    for branch, tracking_ref in _remote_branches(repository):
        branch_parts = branch.split("/")
        if remainder[: len(branch_parts)] == branch_parts:
            source_parts = remainder[len(branch_parts) :]
            matches.append((len(branch_parts), branch, tracking_ref, source_parts))
    if not matches:
        raise ValueError("GitHub skill URL does not reference a current upstream branch")
    _, _, tracking_ref, source_parts = max(matches, key=lambda item: item[0])
    if view == "blob":
        if not source_parts or source_parts[-1] != "SKILL.md":
            raise ValueError("GitHub blob URL must point to SKILL.md")
        source_parts = source_parts[:-1]
    source_path = "/".join(source_parts) if source_parts else "."
    _safe_relative_path(source_path, "source_path", allow_repository_root=True)
    return repository, tracking_ref, source_path


def _license_candidates(source_path: str) -> list[str]:
    source = PurePosixPath(source_path)
    candidates: list[str] = []
    for directory in (source, *source.parents):
        for filename in LICENSE_NAMES:
            if str(directory) == ".":
                candidates.append(filename)
            else:
                candidates.append(str(directory / filename))
    return candidates


def _write_report(path: Path, changes: list[dict[str, str]]) -> None:
    lines = [
        "Automated external skill refresh.",
        "",
        "The harness still records exact Git revisions and content hashes. Review the upstream changes before merging.",
        "",
    ]
    for change in changes:
        lines.append(f"- `{change['name']}`: `{change['old_revision'][:12]}` to `{change['new_revision'][:12]}`")
        github = _github_base(change["repository"])
        if github:
            lines.append(
                f"  - [Upstream comparison]({github}/compare/{change['old_revision']}...{change['new_revision']})"
            )
            lines.append(
                f"  - [Resolved skill source]({github}/tree/{change['new_revision']}/{change['source_path']})"
            )
    if not changes:
        lines.append("No external skill content changed.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _add_resolved_skill(
    manifest_path: Path,
    name: str,
    repository: str,
    tracking_ref: str,
    revision: str,
    source_path: str,
    license_path: str,
) -> dict[str, str]:
    manifest = load_manifest(manifest_path)
    if any(skill["name"] == name for skill in manifest["skills"]):
        raise ValueError(f"external skill already exists: {name}")
    skill = {
        "name": name,
        "repository": repository,
        "tracking_ref": tracking_ref,
        "revision": revision,
        "source_path": source_path,
        "license_path": license_path,
        "content_sha256": "0" * 64,
    }
    validate_manifest({"schema_version": 1, "skills": [skill]})
    with tempfile.TemporaryDirectory(prefix="external-skill-add.") as temp:
        skill["content_sha256"] = materialize_skill(
            skill,
            Path(temp) / name,
            verify_hash=False,
        )
    manifest["skills"].append(skill)
    manifest["skills"].sort(key=lambda item: item["name"])
    _write_manifest(manifest_path, manifest)
    print(f"added {name} at {revision}")
    return skill


def add_skill(
    manifest_path: Path,
    name: str,
    repository: str,
    tracking_ref: str,
    source_path: str,
    license_path: str,
) -> dict[str, str]:
    revision = _resolve_tracking_revision(repository, tracking_ref)
    return _add_resolved_skill(
        manifest_path,
        name,
        repository,
        tracking_ref,
        revision,
        source_path,
        license_path,
    )


def add_skill_from_github_url(
    manifest_path: Path,
    url: str,
    license_path: str | None = None,
    repository_override: str | None = None,
) -> dict[str, str]:
    repository, tracking_ref, source_path = _parse_github_skill_url(
        url,
        repository_override,
    )
    revision = _resolve_tracking_revision(repository, tracking_ref)
    candidates = [license_path] if license_path else _license_candidates(source_path)
    for candidate in candidates:
        _safe_relative_path(candidate, "license_path")
    with tempfile.TemporaryDirectory(prefix="external-skill-url.") as temp:
        checkout = Path(temp) / "repository"
        _checkout_paths(
            repository,
            revision,
            tracking_ref,
            [(source_path, True), *((candidate, False) for candidate in candidates)],
            checkout,
        )
        selected_license = next(
            (candidate for candidate in candidates if (checkout / candidate).is_file()),
            None,
        )
        if selected_license is None:
            raise ValueError(
                "could not find an upstream license; pass --license-path explicitly"
            )
        name = _read_skill_name(checkout / source_path)
    return _add_resolved_skill(
        manifest_path,
        name,
        repository,
        tracking_ref,
        revision,
        source_path,
        selected_license,
    )


def refresh_lock(manifest_path: Path, write: bool, report: Path | None = None) -> int:
    manifest = load_manifest(manifest_path)
    changes: list[dict[str, str]] = []
    for skill in manifest["skills"]:
        candidate_revision = _resolve_tracking_revision(
            skill["repository"], skill["tracking_ref"]
        )
        candidate = dict(skill)
        candidate["revision"] = candidate_revision
        with tempfile.TemporaryDirectory(prefix="external-skill-refresh.") as temp:
            calculated = materialize_skill(
                candidate, Path(temp) / candidate["name"], verify_hash=False
            )
        if calculated == skill["content_sha256"]:
            continue
        changes.append(
            {
                "name": skill["name"],
                "repository": skill["repository"],
                "source_path": skill["source_path"],
                "old_revision": skill["revision"],
                "new_revision": candidate_revision,
                "old_hash": skill["content_sha256"],
                "new_hash": calculated,
            }
        )
        skill["revision"] = candidate_revision
        skill["content_sha256"] = calculated

    if report is not None:
        _write_report(report, changes)
    if changes and write:
        _write_manifest(manifest_path, manifest)
    for change in changes:
        print(
            f"updated {change['name']}: "
            f"{change['old_revision'][:12]} -> {change['new_revision'][:12]}"
        )
    if not changes:
        print("external skill lock is current")
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    materialize = commands.add_parser("materialize")
    materialize.add_argument("--manifest", type=Path, required=True)
    materialize.add_argument("--destination", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--directory", type=Path, required=True)

    digest = commands.add_parser("hash")
    digest.add_argument("--directory", type=Path, required=True)

    add = commands.add_parser("add")
    add.add_argument("--manifest", type=Path, required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--repository", required=True)
    add.add_argument("--tracking-ref", default="refs/heads/main")
    add.add_argument("--source-path", required=True)
    add.add_argument("--license-path", required=True)

    add_url = commands.add_parser("add-url")
    add_url.add_argument("--manifest", type=Path, required=True)
    add_url.add_argument("--url", required=True)
    add_url.add_argument("--license-path")

    refresh = commands.add_parser("refresh-lock")
    refresh.add_argument("--manifest", type=Path, required=True)
    mode = refresh.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    refresh.add_argument("--report", type=Path)

    arguments = parser.parse_args()
    try:
        if arguments.command == "materialize":
            materialize_manifest(arguments.manifest, arguments.destination)
            print(f"resolved external skills into {arguments.destination}")
        elif arguments.command == "verify":
            verify_resolved(arguments.manifest, arguments.directory)
            print(f"verified external skills in {arguments.directory}")
        elif arguments.command == "hash":
            print(tree_hash(arguments.directory))
        elif arguments.command == "add":
            add_skill(
                arguments.manifest,
                arguments.name,
                arguments.repository,
                arguments.tracking_ref,
                arguments.source_path,
                arguments.license_path,
            )
        elif arguments.command == "add-url":
            add_skill_from_github_url(
                arguments.manifest,
                arguments.url,
                arguments.license_path,
            )
        else:
            changed = refresh_lock(
                arguments.manifest, write=arguments.write, report=arguments.report
            )
            if arguments.check and changed:
                return 3
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
