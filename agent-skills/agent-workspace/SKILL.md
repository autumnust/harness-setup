---
name: agent-workspace
description: Create a professional development workspace containing versioned metadata, selected Git repositories, and isolated task worktree containers. Use when the user wants to set up or rehydrate a multi-repository coding environment; do not use for personal task tracking or a change within one existing repository.
---

# Agent Workspace

Create a professional development environment whose root records the workspace
layout while each nested repository keeps its own history and upstream.
`agent-task` is for personal and general task folders; do not use it here.

For example, a workspace with `sdm-benchmark` and `structured-data-models`
contains their normal checkouts plus `sdm-benchmark-worktree/` and
`structured-data-models-worktree/`. A serving task works in
`sdm-benchmark-worktree/serving-measurements/`, leaving the normal checkout on
its primary branch.

## Initialize

1. Resolve the workspace name, destination parent, and repository list. Ask
   for the destination when it is missing. For each repository, collect its
   Git URL, local name, optional primary branch, and role: `active` or
   `reference`.
2. Summarize the proposed destination and repository list before cloning when
   the user has not already authorized creation. The workspace path may already
   exist when it is an empty directory; reject a path that contains files.
3. Run the bundled initializer. A repository specification has the form
   `name|url|branch|role`; omit the last two fields to detect the default
   branch and use `active`.

   ```bash
   python3 <skill-dir>/scripts/hydrate_workspace.py \
     --name "structured-data-models" \
     --destination "/path/to/parent" \
     --repo "sdm-benchmark|ssh://git@example.com/team/sdm-benchmark.git|main|active" \
     --repo "pytorch-geometric|https://github.com/pyg-team/pytorch_geometric.git||reference"
   ```

4. Read the generated `README.md`, `AGENTS.md`, and `workspace.yaml` before
   starting repository work. `workspace.yaml` is the source list for the
   repositories that belong in the workspace. The generated `context/` folder
   stores durable workspace material; `inbox/` holds documents that still need
   review and routing.

The initializer preflights every remote, uses a new or empty target directory,
and initializes the workspace root as a Git repository. If cloning fails after
creation, report the partial workspace and let the user decide whether to retry
or remove it.

## Work in a professional workspace

Follow the workspace `AGENTS.md`. Before changing a nested repository, create
a Git worktree under `<repository>-worktree/<task-name>/`. Keep the named
checkout on its primary branch for inspection, fetches, and creating further
worktrees. Remove a task worktree after merge or abandonment; preserve useful
experiment source on an archive branch first.

Do not add nested repositories, task worktrees, virtual environments, or
generated caches to the workspace root's Git index.
