#!/usr/bin/env python3
"""Create a tracked professional workspace and clone its selected repositories."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
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


def workspace_yaml(name: str, repositories: list[Repository]) -> str:
    lines = ["schema_version: 1", "workspace:", f"  name: {yaml_quote(name)}", "repositories:"]
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

**4. Keep durable context**
Store reviewed design notes, decisions, investigation results, and useful
references in `context/`. Put incoming documents and notes that still need
review in `inbox/`, then move or remove them after processing. Do not create a
`knowledge/` folder for this workspace type.

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


def initialize(name: str, destination: Path, repositories: list[Repository]) -> Path:
    if not destination.is_dir():
        raise ValueError(f"destination does not exist or is not a directory: {destination}")
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError("workspace name may contain letters, digits, dots, underscores, and hyphens")
    if not repositories:
        raise ValueError("at least one repository is required")
    names = [repository.name for repository in repositories]
    if len(names) != len(set(names)):
        raise ValueError("repository names must be unique")

    workspace = destination / name
    if workspace.exists() and not workspace.is_dir():
        raise FileExistsError(f"workspace path is not a directory: {workspace}")
    if workspace.is_dir() and any(workspace.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty workspace: {workspace}")

    for repository in repositories:
        run("git", "ls-remote", "--exit-code", repository.url, "HEAD")

    workspace.mkdir(exist_ok=True)
    (workspace / "context").mkdir()
    (workspace / "inbox").mkdir()
    (workspace / "workspace.yaml").write_text(
        workspace_yaml(name, repositories), encoding="utf-8"
    )
    (workspace / "README.md").write_text(readme(name, repositories), encoding="utf-8")
    (workspace / "AGENTS.md").write_text(agent_instructions(), encoding="utf-8")
    (workspace / ".gitignore").write_text(gitignore(repositories), encoding="utf-8")
    run("git", "init", "-b", "main", str(workspace))

    resolved_repositories: list[Repository] = []
    for repository in repositories:
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
        (workspace / f"{repository.name}-worktree").mkdir()
        resolved_repositories.append(
            Repository(
                name=repository.name,
                url=repository.url,
                branch=branch,
                role=repository.role,
            )
        )

    (workspace / "workspace.yaml").write_text(
        workspace_yaml(name, resolved_repositories), encoding="utf-8"
    )
    (workspace / "README.md").write_text(
        readme(name, resolved_repositories), encoding="utf-8"
    )
    return workspace


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a professional Git workspace with nested repositories."
    )
    parser.add_argument("--name", required=True, help="new workspace folder name")
    parser.add_argument("--destination", required=True, help="existing parent directory")
    parser.add_argument(
        "--repo",
        action="append",
        type=parse_repository,
        default=[],
        help="name|url|branch|role; branch and role are optional",
    )
    arguments = parser.parse_args()
    try:
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
