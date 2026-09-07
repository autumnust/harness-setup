---
name: agent-workspace
description: Create or rehydrate a professional multi-repository development workspace; start, pause, wait, block, resume, finish, or cancel its tasks; and list their filesystem state. Use for explicit workspace task lifecycle requests and active-task discovery; do not use for personal task tracking or a change within one existing repository.
---

# Agent Workspace

An agent workspace records a multi-repository layout. Each nested repository
keeps its own Git history. Use `agent-task` for general or personal work.

## Create or rehydrate

For a new workspace, resolve its name, destination, and repository definitions.
Each repeatable `--repo` value is `name|url|branch|role`; an omitted branch uses
the remote default, and an omitted role means `active`.

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" init \
  --name "<workspace-name>" \
  --destination "<parent>" \
  --repo "<name>|<url>|<branch>|active" \
  --format json
```

Confirm the destination and repositories before cloning unless the user already
did so. The CLI accepts only a new or empty target, checks remotes, clones the
repositories, creates the workspace Git repository, and registers the result.
If it reports a partial result, preserve the folder and report the failed step.

To place an existing workspace on another host, resolve and confirm both paths:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" rehydrate \
  --manifest "/path/to/workspace.yaml" \
  --destination "/exact/path/on/this-host" \
  --format json
```

The CLI rejects unrelated nonempty destinations and verifies existing
repository origins and primary branches before cloning anything missing. Read
the resulting `README.md`, `AGENTS.md`, and `workspace.yaml` before work begins.

## Start and find tasks

Resolve the task name, objective, and any explicit path, TSS host, or session
override. The CLI reads configured defaults:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" start-task \
  --workspace "/path/to/workspace" \
  --name "<task-name>" \
  --objective "<objective>" \
  --format json
```

Use `--execution-folder`, `--tss-host`, or `--session-name` only for overrides.
If a required default is absent, ask for all missing values together; only the
coordinator may save them in global configuration.
The command creates and registers the task, then starts or reuses tmux. A
nonzero result may still contain a valid task folder; report it and retry only
the failed step. The task record stores portable task and workspace IDs without
machine paths; the local catalog maps both IDs to this host's folders. tmux
starts in the workspace root and records the external execution folder
separately. Return that folder and the printed TSS target.

List the workspace's registered tasks with:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-workspace" list-tasks \
  --workspace "/path/to/workspace" \
  --format json
```

Repeat `--status` to filter states. Use `-H` for human terminal output. A saved
TSS target is recorded connection data; listing does not contact TSS. Report
missing registered folders.

Resolve an omitted task name from an explicit name, then a sole matching active
catalog record, then the current tmux task path. Ask when several records still
match.

## Lifecycle and repository work

Use `task-session` only after an explicit request to pause, wait, block, resume,
finish, or cancel. A disconnect, reboot, or missing tmux session does not change
task state. When the coordinator selects the full workflow, it creates the
required execution records after `start-task` succeeds.

Write generated output to the task's execution folder unless the user requests
otherwise. Add durable workspace material to `context/` only when requested.
Before modifying a nested repository, create its task worktree under
`<repository>-worktree/<task-name>/`. Keep the named checkout on its primary
branch. Remove the task worktree after merge or abandonment, preserving useful
experiments on a branch first. Do not add nested repositories, task worktrees,
virtual environments, or generated caches to the workspace root's Git index.
