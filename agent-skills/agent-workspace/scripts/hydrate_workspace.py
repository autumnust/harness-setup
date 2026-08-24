#!/usr/bin/env python3
"""Create a tracked professional workspace and clone its selected repositories."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ROLES = {"active", "reference"}


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    branch: str | None
    role: str


@dataclass(frozen=True)
class WorkspaceManifest:
    name: str
    workspace_id: str
    repositories: list[Repository]


def parse_repository(value: str) -> Repository:
    parts = value.split("|")
    if len(parts) not in {2, 3, 4}:
        raise argparse.ArgumentTypeError(
            "repository must be name|url|branch|role (branch and role are optional)"
        )
    name, url = parts[:2]
    branch = parts[2] if len(parts) >= 3 and parts[2] else None
    role = parts[3] if len(parts) == 4 and parts[3] else "active"
    if not NAME_PATTERN.fullmatch(name):
        raise argparse.ArgumentTypeError(
            "repository name may contain letters, digits, dots, underscores, and hyphens"
        )
    if not url:
        raise argparse.ArgumentTypeError("repository URL cannot be empty")
    if branch and any(character.isspace() for character in branch):
        raise argparse.ArgumentTypeError("branch cannot contain whitespace")
    if role not in ROLES:
        raise argparse.ArgumentTypeError("repository role must be active or reference")
    return Repository(name=name, url=url, branch=branch, role=role)


def run(*command: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def yaml_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def yaml_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def workspace_yaml(
    name: str, workspace_id: str, repositories: list[Repository]
) -> str:
    lines = [
        "schema_version: 2",
        "workspace:",
        f"  id: {yaml_quote(workspace_id)}",
        f"  name: {yaml_quote(name)}",
        "repositories:",
    ]
    for repository in repositories:
        lines.extend(
            [
                f"  - name: {yaml_quote(repository.name)}",
                f"    url: {yaml_quote(repository.url)}",
                f"    branch: {yaml_quote(repository.branch or '')}",
                f"    role: {yaml_quote(repository.role)}",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_workspace_yaml(path: Path) -> WorkspaceManifest:
    if not path.is_file():
        raise ValueError(f"workspace manifest does not exist: {path}")
    name = ""
    workspace_id = ""
    repositories: list[Repository] = []
    current: dict[str, str] | None = None
    section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line == "workspace:":
            section = "workspace"
            continue
        if raw_line == "repositories:":
            if current is not None:
                repositories.append(repository_from_mapping(current, path))
                current = None
            section = "repositories"
            continue
        if section == "workspace" and raw_line.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key == "name":
                name = yaml_unquote(value)
            elif key == "id":
                workspace_id = yaml_unquote(value)
            continue
        if section == "repositories" and raw_line.startswith("  - "):
            if current is not None:
                repositories.append(repository_from_mapping(current, path))
            current = {}
            key, value = stripped[2:].split(":", 1)
            current[key.strip()] = yaml_unquote(value)
            continue
        if section == "repositories" and current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = yaml_unquote(value)
    if current is not None:
        repositories.append(repository_from_mapping(current, path))
    if not name:
        raise ValueError(f"workspace name is missing from {path}")
    if not workspace_id:
        raise ValueError(
            f"workspace id is missing from {path}; initialize or upgrade the manifest first"
        )
    validate_workspace(name, repositories)
    return WorkspaceManifest(name, workspace_id, repositories)


def repository_from_mapping(values: dict[str, str], path: Path) -> Repository:
    name = values.get("name", "")
    url = values.get("url", "")
    branch = values.get("branch") or None
    role = values.get("role") or "active"
    try:
        return parse_repository("|".join((name, url, branch or "", role)))
    except argparse.ArgumentTypeError as exc:
        raise ValueError(f"invalid repository in {path}: {exc}") from exc


def readme(name: str, repositories: list[Repository]) -> str:
    rows = [
        f"| `{repository.name}/` | [{repository.url}]({repository.url}) | {repository.role} |"
        for repository in repositories
    ]
    clone_commands = [f"git clone {repository.url} {repository.name}" for repository in repositories]
    return f"""# {name}

This is a professional development workspace. Its Git repository records the
workspace layout; each nested repository has its own upstream and history.
`workspace.yaml` lists the repositories selected for this workspace.

## Repositories

| Path | Upstream | Role |
|------|----------|------|
{chr(10).join(rows)}

## Working Method

**1. Isolated repository changes**
Keep each named repository checkout on its primary branch and free of task
edits. Before changing a repository, create a dedicated Git worktree at
`<repository>-worktree/<task-name>/` and make the change there. The workspace
root ignores nested repositories and worktree containers.

Remove a task worktree after its change is merged or abandoned. Preserve useful
experiment source on an archive branch before removing its worktree.

**2. Questions-driven scope**
Before changing code, state the concrete questions the work must answer: what a
component owns, what it receives, and what it produces. Keep the work focused
on those questions.

**3. Small examples first**
Use the smallest runnable example that can show the intended behavior before
applying the change to the full system.

**4. Separate execution output from durable context**
Write task plans, logs, evidence, findings, and other execution output to that
task's external execution folder. Put material in `context/` only when the user
explicitly asks to preserve it as durable information for later workspace
tasks. Put incoming documents that still need review in `inbox/`, then move or
remove them after processing. Do not create a `knowledge/` folder for this
workspace type.

**5. Start task executions explicitly**
Use `start-task <task-name>` to create an execution folder under the configured
execution root and start its tmux session. Use `list-tasks` to find execution
folders recorded for this workspace. Workspace-level reusable actions belong in
`workflow/`. Repository worktrees are created later, when a task actually needs
to change that repository.

Use `pause-task`, `wait-task`, `block-task`, or `resume-task` to record an
explicit lifecycle change. Use `finish-task <task-name>` to record a completed
outcome and mark its tmux session for later TSS cleanup. The session remains
available until detached and pruned.

## Rehydrating this workspace

Clone the repositories listed in `workspace.yaml` into this directory:

```bash
{chr(10).join(clone_commands)}
```
"""


def agent_instructions() -> str:
    return """# Workspace instructions

This root repository tracks workspace metadata only. Nested repositories are
tracked by their own upstreams and are ignored here.

When asked to `start-task <task-name>`, use the installed `agent-workspace`
workflow. It creates the execution folder and tmux session but does not create
repository worktrees.

When asked to `list-tasks`, use the same workflow to discover task records for
this workspace. A recorded TSS target is a saved connection value, not a live
session check.

When asked to `finish-task [<task-name>]`, use the same workflow to update the
task record and mark its tmux session for later cleanup without terminating it.

When the user explicitly asks to pause, wait, block, resume, finish, or cancel
a task, use the installed `task-session` lifecycle command. Do not infer a state
change from a conversational stopping point or a missing tmux session.

Task plans, logs, evidence, and findings go to the external execution folder.
Write to `context/` only when the user explicitly asks to preserve information
for reuse by later workspace tasks.

Before changing a nested repository, create a Git worktree under
`<repository>-worktree/<task-name>/`. Do not edit the named repository checkout
for task work. Remove task worktrees after merge or abandonment, retaining
useful experiment source on an archive branch when needed.

Read each repository's local agent instructions before making changes.
"""


def gitignore(repositories: list[Repository]) -> str:
    entries = [
        "# Nested repositories are tracked separately.",
        *[f"{repository.name}/" for repository in repositories],
        "",
        "# Agent-created Git worktree containers are local only.",
        "/*-worktree/",
        "",
        "# Common local artifacts.",
        ".venv/",
        "__pycache__/",
        "*.py[cod]",
        ".DS_Store",
        "",
    ]
    return "\n".join(entries)


def validate_workspace(name: str, repositories: list[Repository]) -> None:
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError("workspace name may contain letters, digits, dots, underscores, and hyphens")
    if not repositories:
        raise ValueError("at least one repository is required")
    names = [repository.name for repository in repositories]
    if len(names) != len(set(names)):
        raise ValueError("repository names must be unique")


def preflight_repositories(repositories: list[Repository]) -> None:
    for repository in repositories:
        run("git", "ls-remote", "--exit-code", repository.url, "HEAD")


def write_workspace_files(
    workspace: Path,
    name: str,
    workspace_id: str,
    repositories: list[Repository],
) -> None:
    (workspace / "context").mkdir(exist_ok=True)
    (workspace / "inbox").mkdir(exist_ok=True)
    (workspace / "workflow").mkdir(exist_ok=True)
    workflow_readme = workspace / "workflow" / "README.md"
    if not workflow_readme.exists():
        workflow_readme.write_text(
            "# Workspace workflows\n\n"
            "Keep reusable workspace-level procedures and actions here.\n",
            encoding="utf-8",
        )
    (workspace / "workspace.yaml").write_text(
        workspace_yaml(name, workspace_id, repositories), encoding="utf-8"
    )
    (workspace / "README.md").write_text(readme(name, repositories), encoding="utf-8")
    (workspace / "AGENTS.md").write_text(agent_instructions(), encoding="utf-8")
    (workspace / ".gitignore").write_text(gitignore(repositories), encoding="utf-8")


def clone_repository(workspace: Path, repository: Repository) -> Repository:
    command = ["git", "clone"]
    if repository.branch:
        command.extend(["--branch", repository.branch, "--single-branch"])
    command.extend([repository.url, repository.name])
    run(*command, cwd=workspace)
    branch = repository.branch or run(
        "git", "branch", "--show-current", cwd=workspace / repository.name
    ).stdout.strip()
    if not branch:
        raise RuntimeError(f"could not determine primary branch for {repository.name}")
    (workspace / f"{repository.name}-worktree").mkdir(exist_ok=True)
    return Repository(repository.name, repository.url, branch, repository.role)


def initialize(name: str, destination: Path, repositories: list[Repository]) -> Path:
    if not destination.is_dir():
        raise ValueError(f"destination does not exist or is not a directory: {destination}")
    validate_workspace(name, repositories)

    workspace = destination / name
    if workspace.exists() and not workspace.is_dir():
        raise FileExistsError(f"workspace path is not a directory: {workspace}")
    if workspace.is_dir() and any(workspace.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty workspace: {workspace}")

    preflight_repositories(repositories)

    workspace_id = str(uuid.uuid4())
    workspace.mkdir(exist_ok=True)
    write_workspace_files(workspace, name, workspace_id, repositories)
    run("git", "init", "-b", "main", str(workspace))

    resolved_repositories: list[Repository] = []
    for repository in repositories:
        resolved_repositories.append(clone_repository(workspace, repository))

    (workspace / "workspace.yaml").write_text(
        workspace_yaml(name, workspace_id, resolved_repositories), encoding="utf-8"
    )
    (workspace / "README.md").write_text(
        readme(name, resolved_repositories), encoding="utf-8"
    )
    return workspace


def same_repository(left: Repository, right: Repository) -> bool:
    return (
        left.name == right.name
        and left.url.rstrip("/") == right.url.rstrip("/")
        and left.branch == right.branch
        and left.role == right.role
    )


def validate_existing_repository(workspace: Path, repository: Repository) -> None:
    repository_path = workspace / repository.name
    if not repository_path.is_dir():
        raise ValueError(f"repository path is not a directory: {repository_path}")
    inside = run("git", "rev-parse", "--is-inside-work-tree", cwd=repository_path)
    if inside.stdout.strip() != "true":
        raise ValueError(f"repository path is not a Git checkout: {repository_path}")
    remote = run("git", "remote", "get-url", "origin", cwd=repository_path).stdout.strip()
    if remote.rstrip("/") != repository.url.rstrip("/"):
        raise ValueError(
            f"repository origin does not match workspace.yaml for {repository.name}: {remote}"
        )
    branch = run("git", "branch", "--show-current", cwd=repository_path).stdout.strip()
    if repository.branch and branch != repository.branch:
        raise ValueError(
            f"repository branch does not match workspace.yaml for {repository.name}: {branch}"
        )
    container = workspace / f"{repository.name}-worktree"
    if container.exists() and not container.is_dir():
        raise ValueError(f"worktree container is not a directory: {container}")


def rehydrate(manifest_path: Path, destination: Path) -> Path:
    manifest_path = manifest_path.expanduser().resolve()
    destination = destination.expanduser()
    if not destination.is_absolute():
        raise ValueError(f"rehydration destination must be absolute: {destination}")
    destination = destination.resolve()
    manifest = parse_workspace_yaml(manifest_path)
    if not destination.exists() and not destination.parent.is_dir():
        raise ValueError(f"destination parent does not exist: {destination.parent}")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"destination is not a directory: {destination}")

    existing_manifest_path = destination / "workspace.yaml"
    if destination.is_dir() and any(destination.iterdir()):
        if not existing_manifest_path.is_file():
            raise FileExistsError(
                f"nonempty destination has no workspace.yaml: {destination}"
            )
        existing = parse_workspace_yaml(existing_manifest_path)
        if existing.workspace_id != manifest.workspace_id:
            raise ValueError("destination contains a different workspace id")
        if existing.name != manifest.name or len(existing.repositories) != len(
            manifest.repositories
        ):
            raise ValueError("destination workspace metadata does not match the source")
        if any(
            not same_repository(left, right)
            for left, right in zip(existing.repositories, manifest.repositories)
        ):
            raise ValueError("destination repository metadata does not match the source")

    for repository in manifest.repositories:
        repository_path = destination / repository.name
        if repository_path.exists():
            validate_existing_repository(destination, repository)
    preflight_repositories(manifest.repositories)

    new_destination = not destination.exists() or not any(destination.iterdir())
    destination.mkdir(exist_ok=True)
    if new_destination:
        write_workspace_files(
            destination,
            manifest.name,
            manifest.workspace_id,
            manifest.repositories,
        )
        run("git", "init", "-b", "main", str(destination))

    for repository in manifest.repositories:
        if not (destination / repository.name).exists():
            clone_repository(destination, repository)
        else:
            (destination / f"{repository.name}-worktree").mkdir(exist_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or rehydrate a professional Git workspace."
    )
    parser.add_argument("--name", help="new workspace folder name")
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--rehydrate-from",
        type=Path,
        help="workspace.yaml to recreate at the exact destination path",
    )
    parser.add_argument(
        "--repo",
        action="append",
        type=parse_repository,
        default=[],
        help="name|url|branch|role; branch and role are optional",
    )
    arguments = parser.parse_args()
    try:
        if arguments.rehydrate_from:
            if arguments.name or arguments.repo:
                raise ValueError(
                    "--rehydrate-from cannot be combined with --name or --repo"
                )
            workspace = rehydrate(
                arguments.rehydrate_from, Path(arguments.destination)
            )
        else:
            if not arguments.name:
                raise ValueError("--name is required when creating a workspace")
            workspace = initialize(
                arguments.name, Path(arguments.destination).expanduser(), arguments.repo
            )
    except (FileExistsError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(workspace.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
