#!/usr/bin/env python3
"""Register and discover local agent tasks and workspaces."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
DEFAULT_HARNESS_HOME = Path(
    os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness")
)
DEFAULT_DATABASE = DEFAULT_HARNESS_HOME / "state/task-catalog/catalog.sqlite3"
IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
}
STATUS_ORDER = {
    "blocked": 0,
    "active": 1,
    "waiting": 2,
    "paused": 3,
    "done": 4,
    "cancelled": 5,
    "archived": 6,
    "unknown": 7,
    "": 8,
}


# Every catalog listing runs this exact parameter-free statement. Filtering and
# ordering happen after SQLite returns the complete local catalog.
DISCOVERY_SELECT = """
SELECT
    'workspace' AS record_type,
    'agent-workspace' AS kind,
    w.id AS id,
    w.name AS name,
    w.name AS title,
    w.id AS workspace_id,
    w.name AS workspace_name,
    wl.path AS path,
    wl.present AS present,
    '' AS status,
    '' AS created,
    wl.updated_at AS updated,
    wl.last_used_at AS last_used,
    '' AS runtime_host,
    '' AS tmux_session,
    '' AS tss_target,
    '' AS objective,
    '' AS current_state,
    '' AS next_task,
    wl.git_root AS git_root,
    wl.git_remote AS git_remote,
    wl.git_commit AS git_commit,
    wl.last_seen AS last_seen
FROM workspaces AS w
JOIN workspace_locations AS wl ON wl.workspace_id = w.id
UNION ALL
SELECT
    'task' AS record_type,
    t.kind AS kind,
    t.id AS id,
    tl.title AS name,
    tl.title AS title,
    t.workspace_id AS workspace_id,
    COALESCE(w.name, tl.workspace_name, '') AS workspace_name,
    tl.path AS path,
    tl.present AS present,
    tl.status AS status,
    tl.created AS created,
    tl.updated AS updated,
    tl.last_used_at AS last_used,
    COALESCE(s.runtime_host, '') AS runtime_host,
    COALESCE(s.tmux_session, '') AS tmux_session,
    COALESCE(s.tss_target, '') AS tss_target,
    tl.objective AS objective,
    tl.current_state AS current_state,
    tl.next_task AS next_task,
    tl.git_root AS git_root,
    tl.git_remote AS git_remote,
    tl.git_commit AS git_commit,
    tl.last_seen AS last_seen
FROM tasks AS t
JOIN task_locations AS tl ON tl.task_id = t.id
LEFT JOIN workspaces AS w ON w.id = t.workspace_id
LEFT JOIN sessions AS s ON s.task_location_id = tl.id
"""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS catalog_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_locations (
    id INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    path TEXT NOT NULL UNIQUE,
    present INTEGER NOT NULL CHECK (present IN (0, 1)),
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    git_root TEXT NOT NULL,
    git_remote TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    UNIQUE (workspace_id, path)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('agent-task', 'workspace-task')),
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE TABLE IF NOT EXISTS task_locations (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    workspace_name TEXT NOT NULL,
    present INTEGER NOT NULL CHECK (present IN (0, 1)),
    status TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    objective TEXT NOT NULL,
    current_state TEXT NOT NULL,
    next_task TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    git_root TEXT NOT NULL,
    git_remote TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    UNIQUE (task_id, path)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    task_location_id INTEGER NOT NULL UNIQUE REFERENCES task_locations(id)
        ON DELETE CASCADE,
    runtime_host TEXT NOT NULL,
    tmux_session TEXT NOT NULL,
    tss_target TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

INSERT INTO catalog_metadata(key, value)
VALUES ('schema_version', '1')
ON CONFLICT(key) DO UPDATE SET value = excluded.value;
"""


class CatalogError(ValueError):
    """A user-correctable catalog operation failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def yaml_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return decoded if isinstance(decoded, str) else str(decoded)
    return "" if value in {"null", "~"} else value


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(
            index for index in range(1, len(lines)) if lines[index].strip() == "---"
        )
    except StopIteration:
        return {}, text
    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = yaml_unquote(value)
    return metadata, "\n".join(lines[end + 1 :])


def markdown_section(text: str, *titles: str) -> str:
    wanted = {f"## {title}".casefold() for title in titles}
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip().casefold() in wanted:
            start = index + 1
            break
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            collected.append(line.strip())
    return " ".join(collected)


def parse_workspace_manifest(path: Path) -> dict[str, str]:
    workspace_id = ""
    name = ""
    section = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CatalogError(f"cannot read workspace manifest {path}: {exc}") from exc
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line == "workspace:":
            section = "workspace"
            continue
        if raw_line and not raw_line.startswith(" "):
            section = ""
            continue
        if section == "workspace" and raw_line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key == "id":
                workspace_id = yaml_unquote(value)
            elif key == "name":
                name = yaml_unquote(value)
    if not name:
        raise CatalogError(f"workspace manifest needs workspace.name: {path}")
    if not workspace_id:
        workspace_id = legacy_workspace_id(path.parent)
    return {"id": workspace_id, "name": name}


def normalized_git_remote(remote: str) -> str:
    remote = remote.strip()
    if "://" not in remote and ":" in remote:
        owner, repository = remote.split(":", 1)
        host = owner.rsplit("@", 1)[-1].lower()
        value = f"{host}/{repository.lstrip('/')}"
    elif "://" in remote:
        parsed = urlsplit(remote)
        host = (parsed.hostname or "").lower()
        value = f"{host}/{parsed.path.lstrip('/')}"
    else:
        value = str(Path(remote).expanduser().resolve())
    return value.removesuffix(".git").rstrip("/")


def legacy_workspace_id(path: Path) -> str:
    remote = run_git(path, "remote", "get-url", "origin")
    if remote:
        value = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"agent-workspace:{normalized_git_remote(remote)}",
        )
        return f"legacy-origin:{value}"
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"agent-workspace-local:{path.resolve()}")
    return f"legacy-local:{value}"


def parse_task_readme(path: Path) -> dict[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CatalogError(f"cannot read task README {path}: {exc}") from exc
    metadata, body = parse_front_matter(text)
    if metadata.get("agent_task") == "1":
        kind = "agent-task"
    elif metadata.get("workspace_task") == "1":
        kind = "workspace-task"
    else:
        return None
    task_id = metadata.get("id", "")
    if not task_id:
        raise CatalogError(f"task README needs a stable id: {path}")
    workspace_id = metadata.get("workspace_id", "")
    workspace_name = metadata.get("workspace", "")
    workspace_path = metadata.get("workspace_path", "")
    if kind == "workspace-task" and workspace_path:
        candidate = Path(workspace_path).expanduser()
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        manifest_path = candidate.resolve() / "workspace.yaml"
        if manifest_path.is_file():
            manifest = parse_workspace_manifest(manifest_path)
            if workspace_id and workspace_id != manifest["id"]:
                raise CatalogError(
                    f"workspace_id in task does not match {manifest_path}: {workspace_id}"
                )
            workspace_id = manifest["id"]
            workspace_name = manifest["name"]
            workspace_path = str(candidate.resolve())
    if kind == "workspace-task" and not workspace_id:
        raise CatalogError(
            f"workspace task README needs workspace_id or a readable workspace_path: {path}"
        )
    runtime_host = metadata.get("runtime_host", "")
    tmux_session = metadata.get("tmux_session", "")
    return {
        "id": task_id,
        "kind": kind,
        "title": metadata.get("title") or metadata.get("task_name") or path.parent.name,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "workspace_path": workspace_path,
        "status": metadata.get("status", "unknown"),
        "created": metadata.get("created", ""),
        "updated": metadata.get("updated", ""),
        "last_used_at": metadata.get("last_used_at", ""),
        "runtime_host": runtime_host,
        "tmux_session": tmux_session,
        "tss_target": (
            f"{runtime_host}:{tmux_session}"
            if runtime_host and tmux_session
            else ""
        ),
        "objective": markdown_section(body, "Current objective", "Goal"),
        "current_state": markdown_section(body, "Current state"),
        "next_task": markdown_section(body, "Immediate next task"),
    }


def run_git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=False,
        text=True,
        capture_output=True,
        timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_metadata(path: Path) -> dict[str, str]:
    root = run_git(path, "rev-parse", "--show-toplevel")
    if not root:
        return {"git_root": "", "git_remote": "", "git_commit": ""}
    git_root = str(Path(root).resolve())
    return {
        "git_root": git_root,
        "git_remote": run_git(Path(git_root), "remote", "get-url", "origin"),
        "git_commit": run_git(Path(git_root), "rev-parse", "HEAD"),
    }


def connect(database: Path) -> sqlite3.Connection:
    database = database.expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    with connection:
        connection.executescript(SCHEMA_SQL)
    return connection


def begin_write(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def upsert_workspace(
    connection: sqlite3.Connection,
    path: Path,
    manifest: dict[str, str],
    observed_at: str,
) -> None:
    git = git_metadata(path)
    connection.execute(
        """
        INSERT INTO workspaces(id, name) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET name = excluded.name
        """,
        (manifest["id"], manifest["name"]),
    )
    connection.execute(
        """
        INSERT INTO workspace_locations(
            workspace_id, path, present, registered_at, updated_at,
            last_used_at, last_seen, git_root, git_remote, git_commit
        ) VALUES (?, ?, 1, ?, ?, '', ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            workspace_id = excluded.workspace_id,
            present = 1,
            updated_at = excluded.updated_at,
            last_seen = excluded.last_seen,
            git_root = excluded.git_root,
            git_remote = excluded.git_remote,
            git_commit = excluded.git_commit
        """,
        (
            manifest["id"],
            str(path),
            observed_at,
            observed_at,
            observed_at,
            git["git_root"],
            git["git_remote"],
            git["git_commit"],
        ),
    )


def register_workspace_reference(
    connection: sqlite3.Connection,
    task: dict[str, str],
    observed_at: str,
) -> None:
    workspace_id = task["workspace_id"]
    if not workspace_id:
        return
    workspace_name = task["workspace_name"] or workspace_id
    workspace_path = task["workspace_path"]
    if workspace_path:
        candidate = Path(workspace_path).expanduser().resolve()
        manifest_path = candidate / "workspace.yaml"
        if manifest_path.is_file():
            manifest = parse_workspace_manifest(manifest_path)
            if manifest["id"] != workspace_id:
                raise CatalogError(
                    f"workspace_id in task does not match {manifest_path}: {workspace_id}"
                )
            upsert_workspace(connection, candidate, manifest, observed_at)
            return
    connection.execute(
        """
        INSERT INTO workspaces(id, name) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = CASE
                WHEN workspaces.name = workspaces.id THEN excluded.name
                ELSE workspaces.name
            END
        """,
        (workspace_id, workspace_name),
    )


def upsert_task(
    connection: sqlite3.Connection,
    path: Path,
    task: dict[str, str],
    observed_at: str,
) -> None:
    register_workspace_reference(connection, task, observed_at)
    git = git_metadata(path)
    workspace_id = task["workspace_id"] or None
    connection.execute(
        """
        INSERT INTO tasks(id, kind, workspace_id) VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            kind = excluded.kind,
            workspace_id = excluded.workspace_id
        """,
        (task["id"], task["kind"], workspace_id),
    )
    connection.execute(
        """
        DELETE FROM sessions
        WHERE task_location_id IN (SELECT id FROM task_locations WHERE path = ?)
        """,
        (str(path),),
    )
    connection.execute(
        """
        INSERT INTO task_locations(
            task_id, path, title, workspace_name, present, status, created,
            updated, last_used_at, objective, current_state, next_task,
            registered_at, last_seen, git_root, git_remote, git_commit
        ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            task_id = excluded.task_id,
            title = excluded.title,
            workspace_name = excluded.workspace_name,
            present = 1,
            status = excluded.status,
            created = excluded.created,
            updated = excluded.updated,
            last_used_at = excluded.last_used_at,
            objective = excluded.objective,
            current_state = excluded.current_state,
            next_task = excluded.next_task,
            last_seen = excluded.last_seen,
            git_root = excluded.git_root,
            git_remote = excluded.git_remote,
            git_commit = excluded.git_commit
        """,
        (
            task["id"],
            str(path),
            task["title"],
            task["workspace_name"],
            task["status"],
            task["created"],
            task["updated"],
            task["last_used_at"],
            task["objective"],
            task["current_state"],
            task["next_task"],
            observed_at,
            observed_at,
            git["git_root"],
            git["git_remote"],
            git["git_commit"],
        ),
    )
    if task["runtime_host"] or task["tmux_session"]:
        connection.execute(
            """
            INSERT INTO sessions(
                task_id, task_location_id, runtime_host, tmux_session,
                tss_target, observed_at
            )
            SELECT ?, id, ?, ?, ?, ? FROM task_locations WHERE path = ?
            ON CONFLICT(task_location_id) DO UPDATE SET
                task_id = excluded.task_id,
                runtime_host = excluded.runtime_host,
                tmux_session = excluded.tmux_session,
                tss_target = excluded.tss_target,
                observed_at = excluded.observed_at
            """,
            (
                task["id"],
                task["runtime_host"],
                task["tmux_session"],
                task["tss_target"],
                observed_at,
                str(path),
            ),
        )


def classify_path(path: Path) -> tuple[str, dict[str, str]]:
    workspace_file = path / "workspace.yaml"
    if workspace_file.is_file():
        return "workspace", parse_workspace_manifest(workspace_file)
    readme = path / "README.md"
    if readme.is_file():
        task = parse_task_readme(readme)
        if task is not None:
            return "task", task
    raise CatalogError(f"no recognized workspace.yaml or task README.md at {path}")


def register_path(connection: sqlite3.Connection, raw_path: Path) -> dict[str, Any]:
    source = raw_path.expanduser()
    if source.name in {"workspace.yaml", "README.md"} and source.is_file():
        source = source.parent
    path = source.resolve()
    if not path.is_dir():
        raise CatalogError(f"registration path is not a directory: {path}")
    record_type, parsed = classify_path(path)
    observed_at = utc_now()
    begin_write(connection)
    try:
        if record_type == "workspace":
            upsert_workspace(connection, path, parsed, observed_at)
        else:
            upsert_task(connection, path, parsed, observed_at)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    records = discovery_records(connection)
    return next(
        record
        for record in records
        if record["record_type"] == record_type and record["path"] == str(path)
    )


def discovery_records(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(DISCOVERY_SELECT).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        record = {key: ("" if row[key] is None else row[key]) for key in row.keys()}
        record["present"] = bool(record["present"])
        records.append(record)
    return sorted(
        records,
        key=lambda record: (
            0 if record["record_type"] == "workspace" else 1,
            STATUS_ORDER.get(str(record["status"]), STATUS_ORDER["unknown"]),
            str(record["name"]).casefold(),
            str(record["path"]),
        ),
    )


def filter_records(
    records: Iterable[dict[str, Any]],
    kind: str | None,
    workspace_id: str | None,
) -> list[dict[str, Any]]:
    filtered = list(records)
    if kind:
        if kind == "workspace":
            filtered = [record for record in filtered if record["record_type"] == "workspace"]
        elif kind == "task":
            filtered = [record for record in filtered if record["record_type"] == "task"]
        else:
            filtered = [record for record in filtered if record["kind"] == kind]
    if workspace_id:
        filtered = [
            record for record in filtered if record["workspace_id"] == workspace_id
        ]
    return filtered


def render_markdown(records: Sequence[dict[str, Any]]) -> str:
    if not records:
        return "No registered agent tasks or workspaces found."
    lines = [
        "| Type | Kind | Status | Name | Workspace | Session | Present | Path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        values = (
            record["record_type"],
            record["kind"],
            record["status"],
            record["name"],
            record["workspace_name"],
            record["tss_target"],
            "yes" if record["present"] else "no",
            record["path"],
        )
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def json_payload(
    database: Path,
    records: Sequence[dict[str, Any]],
    *,
    command: str,
    roots: Sequence[Path] = (),
) -> str:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "database": str(database.expanduser().resolve()),
        "records": list(records),
    }
    if roots:
        payload["roots"] = [str(root) for root in roots]
    return json.dumps(payload, indent=2, sort_keys=True)


def scan_roots(connection: sqlite3.Connection, roots: Sequence[Path]) -> int:
    registered = 0
    for root in roots:
        for current, directories, files in os.walk(root):
            directories[:] = sorted(
                name
                for name in directories
                if name not in IGNORED_DIRECTORIES and not name.endswith("-worktree")
            )
            current_path = Path(current).resolve()
            recognized = False
            if "workspace.yaml" in files:
                try:
                    manifest = parse_workspace_manifest(current_path / "workspace.yaml")
                except CatalogError:
                    pass
                else:
                    observed_at = utc_now()
                    upsert_workspace(connection, current_path, manifest, observed_at)
                    registered += 1
                    recognized = True
            if "README.md" in files:
                try:
                    task = parse_task_readme(current_path / "README.md")
                except CatalogError:
                    task = None
                if task is not None:
                    observed_at = utc_now()
                    upsert_task(connection, current_path, task, observed_at)
                    registered += 1
                    recognized = True
                    directories[:] = []
            if recognized:
                directories[:] = sorted(directories)
    return registered


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def reconcile(connection: sqlite3.Connection, raw_roots: Sequence[Path]) -> tuple[list[Path], int]:
    roots: list[Path] = []
    for raw_root in raw_roots:
        root = raw_root.expanduser().resolve()
        if not root.is_dir():
            raise CatalogError(f"reconciliation root is not a directory: {root}")
        if root not in roots:
            roots.append(root)
    before = discovery_records(connection)
    begin_write(connection)
    try:
        count = scan_roots(connection, roots)
        for record in before:
            path = Path(record["path"])
            if any(within(path, root) for root in roots):
                present = int(path.is_dir())
                table = (
                    "workspace_locations"
                    if record["record_type"] == "workspace"
                    else "task_locations"
                )
                connection.execute(
                    f"UPDATE {table} SET present = ? WHERE path = ?",  # table is internal
                    (present, str(path)),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return roots, count


def add_listing_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--kind",
        choices=("workspace", "task", "agent-workspace", "agent-task", "workspace-task"),
    )
    parser.add_argument("--workspace-id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="register one local folder")
    register.add_argument("--path", required=True, type=Path)
    register.add_argument("--format", choices=("json", "markdown"), default="json")

    listing = commands.add_parser("list", help="list registered local folders")
    add_listing_arguments(listing)

    export = commands.add_parser("export", help="export records for another host")
    add_listing_arguments(export)
    export.set_defaults(format="json")

    repair = commands.add_parser("reconcile", help="scan explicit roots and refresh the catalog")
    repair.add_argument("roots", nargs="+", type=Path)
    repair.add_argument("--format", choices=("json", "markdown"), default="markdown")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        with connect(args.db) as connection:
            if args.command == "register":
                record = register_path(connection, args.path)
                records = [record]
                roots: list[Path] = []
            elif args.command == "reconcile":
                roots, _count = reconcile(connection, args.roots)
                records = discovery_records(connection)
            else:
                roots = []
                records = filter_records(
                    discovery_records(connection), args.kind, args.workspace_id
                )
        if args.format == "json":
            print(json_payload(args.db, records, command=args.command, roots=roots))
        else:
            print(render_markdown(records))
        return 0
    except (CatalogError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
