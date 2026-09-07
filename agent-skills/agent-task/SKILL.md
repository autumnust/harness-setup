---
name: agent-task
description: Initialize, operate, discover, summarize, and run portable filesystem-backed task workspaces with TSS-reachable tmux sessions and explicit lifecycle state. Use for personal or professional task folders that are not multi-repository development workspaces.
---

# Agent Task

The task folder and its Git history are authoritative. The machine-local SQLite
catalog records this host's path and session data.

## Create a task

Resolve the name, objective, destination, and any TSS host or session override,
then run:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" init \
  --name "<folder-name>" \
  --objective "<objective>" \
  --destination "<existing-parent>" \
  --format json
```

The CLI reads the default TSS host from
`$AGENT_HARNESS_HOME/config.json`, with `AGENT_HARNESS_HOME` defaulting to
`~/.agent-harness`. Pass `--tss-host` or `--session-name` only for an override.
If required values remain unresolved, ask for them together.

The CLI creates the folder, registers it, and starts tmux. A nonzero result may
still contain a valid folder; use `catalog_registered` and `session_started` to
identify the failed step, and retry only that step. Never rerun `init` against
an existing path.

Read the generated `README.md`, `tasks.md`, `AGENTS.md`, and relevant context
before starting work. Return the task path and printed TSS target.

## Find tasks

Use JSON for agent or script consumption:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" list \
  [<root> ...] --format json
```

Use `-H` for human terminal output. A root filters registered paths; it does not
scan the filesystem. Only repair registration after a manual copy, move, or old
installation:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" reconcile \
  <root> [<root> ...] --format json
```

Report blocked tasks first, followed by active, waiting, paused, done,
cancelled, and archived tasks. Treat missing or stale metadata as unknown.

## Work and lifecycle

Follow the task's `AGENTS.md`. Keep `README.md` status, updated date, current
state, and immediate next task current. Preserve its stable ID.

Initialization starts the session. Use `task-session` only to restore a missing
session or apply an explicit request to pause, wait, block, resume, finish, or
cancel. Ending a conversation, losing tmux, or rebooting does not change task
state. Leave finished sessions available for inspection; TSS may remove them
later with `tss prune --finished`.
