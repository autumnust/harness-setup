---
name: agent-workspace
description: Create or rehydrate a professional multi-repository development workspace; start, pause, wait, block, resume, finish, or cancel its tasks; and list their filesystem state. Use for explicit workspace task lifecycle requests and active-task discovery; do not use for personal task tracking or a change within one existing repository.
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
3. Run the installed CLI. A repository specification has the form
   `name|url|branch|role`; omit the last two fields to detect the default
   branch and use `active`.

   ```bash
   "${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" init \
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

## Rehydrate on another host

When the user asks to rehydrate or place an existing workspace on this host,
ask for the exact destination path. Also resolve the source `workspace.yaml`.
Show both paths before making changes.

Check that the destination parent exists. A new or empty destination is valid.
A nonempty destination is valid only when it contains the same workspace ID and
repository definitions. Existing repository folders must be Git checkouts whose
`origin` URL and current primary branch match the manifest. The helper performs
these checks before cloning missing repositories:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" rehydrate \
  --manifest "/path/to/source/workspace.yaml" \
  --destination "/exact/path/on/this/host"
```

Never reuse an unrelated nonempty directory. A stable workspace ID makes task
discovery portable even when the absolute workspace path differs by host.

## Start a task

Use this workflow when the user says `start-task <task-name>` from an initialized
workspace. This operation creates a minimal task record and a tmux session; it
does not create repository worktrees or the full long-running-work structure.

1. Resolve the task name and a one-sentence objective.
2. Read `$AGENT_HARNESS_HOME/config.json`, defaulting `AGENT_HARNESS_HOME` to
   `~/.agent-harness`. Use `execution_root/<task-name>` as the proposed execution
   folder. Let the user supply a different absolute folder.
3. Resolve the TSS host label from `task_runtime.tss.host_alias` when configured,
   and default the tmux session name to the task name. Ask for all missing or
   overridden values together and show the proposed folder before creating it.
   When `execution_root` or the host label is missing, offer to save the
   confirmed value as this machine's default; only the coordinator writes the
   mutable runtime configuration.
4. Run the installed CLI. This command creates the durable task record,
   registers its local path, and starts or reuses its tmux session:

   ```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" start-task \
  --workspace "/path/to/workspace" \
  --name "<task-name>" \
  --objective "<objective>" \
  --tss-host "<tss-host-label>"
   ```

   Pass `--execution-folder "/other/path"` when the user overrides the default.
   The task `README.md` contains the portable task and workspace IDs, but no
   machine path. The host-local catalog records both local folders. The tmux
   working directory is the workspace root; `@agent_task_path` points to the
   external execution folder. Return the execution-folder path and the printed
   `tss <host>:<session>` command.
5. When the coordinator selects the full workflow, create its canonical
   execution entry points and then invoke the execution-environment preparation
   flow. Fast tasks keep only the minimal task record unless their work needs
   additional files.

If session setup fails, the CLI leaves the initialized and registered execution
folder in place and returns a nonzero status with the exact failure. Report the
folder so the user can retry. Do not remove it unless the user asks.

## List tasks

Use this workflow when the user says `list-tasks` from an initialized workspace.
Run the installed CLI:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" list-tasks \
  --workspace "/path/to/workspace" \
  -H
```

When the user asks for active tasks, pass `--status active`. Repeat `--status`
to include several requested states. Use `--format json` for agent or script
consumption. Use `-H` or `--human` for wrapped terminal output.

The CLI queries the machine-local SQLite catalog and filters the returned rows
by the workspace's stable ID. It does not scan the execution root. Results are
ordered by each task's own `last_used_at` value, newest first. The task README
and its Git history remain authoritative for task state; SQLite records where
this host has materialized the workspace and task. A displayed TSS target is a
saved connection value; this listing does not contact TSS or confirm that the
session is running. Report registered folders that are no longer present.

Resolve an omitted task name in this order: an explicit name, the sole matching
active task from `agent-workspace list-tasks`, then the current tmux task path as a
runtime hint. If multiple filesystem records still match, ask which task the
user means.

## Change task state

Only change lifecycle state from an explicit user request. Phrases such as
"pause this task", "wait for review", "this is blocked", "resume the task",
"finish this task", and "cancel this task" are explicit. Ending a conversation,
disconnecting TSS, losing tmux, or rebooting a host does not change task state.

Resolve the execution folder with the list workflow, then use the installed
`task-session` state workflow. For `paused`, `waiting`, `blocked`, and `active`,
collect a current-state summary plus a concrete next step or resume trigger.
For `done` or `cancelled`, collect the outcome. The helper writes the task file
first and then mirrors the state into tmux when the recorded session exists.

## Finish a task

When the user says `finish-task [<task-name>]`, resolve the execution folder
with workspace task discovery, summarize the outcome, and use the installed
`task-session` finish workflow. It updates the filesystem state and marks the
tmux session for later `tss prune --finished` cleanup without terminating it.

## Work in a professional workspace

Follow the workspace `AGENTS.md`. Unless the user asks otherwise, write
generated output to the current task's execution folder, not the workspace.

Before changing a nested repository, create a Git worktree under
`<repository>-worktree/<task-name>/`. Keep the named checkout on its primary
branch for inspection, fetches, and creating further worktrees. Remove a task
worktree after merge or abandonment; preserve useful experiment source on an
archive branch first.

Do not add nested repositories, task worktrees, virtual environments, or
generated caches to the workspace root's Git index.
