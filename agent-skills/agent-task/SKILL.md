---
name: agent-task
description: Create, discover, and update portable filesystem-backed task contexts. Use for general or personal tasks that are not explicit multi-repository agent-workspace tasks.
---

# Agent task

The folder and its Git history are the durable task record. Runtime sessions are
optional and managed separately.

## Create

Resolve the name, objective, and existing parent directory, then run:

```bash
agent-task init \
  --name "<folder-name>" \
  --objective "<objective>" \
  --destination "<parent>" \
  --format json
```

The command creates and registers the folder. If registration fails, preserve
the folder and report `task-catalog register --path <folder>` as the repair.
Never rerun `init` against an existing path. Read its `README.md`, `tasks.md`,
`AGENTS.md`, and relevant context before work.

## Discover or import

```bash
agent-task list [<root> ...] --format json
agent-task reconcile <root> [<root> ...] --format json
```

Use `-H` for direct terminal reading. Roots filter registered paths; only
`reconcile` scans them. Reconcile after an old installation or a manual copy or
move.

## Change lifecycle state

Only after explicit user intent, map start or resume to `active`, pause to
`paused`, waiting to `waiting`, a blocker to `blocked`, finish to `done`, and
cancel or abandon to `cancelled`, then run:

```bash
agent-task set-state \
  --task-dir "<folder>" \
  --status active|paused|waiting|blocked|done|cancelled \
  --summary "<current state or outcome>" \
  --next-step "<next action or resume trigger>" \
  --format json
```

`active`, `paused`, `waiting`, and `blocked` require `--next-step`; terminal
states do not. The operation works for general and workspace tasks. A stopped
agent process, lost tmux server, reboot, or conversation ending does not change
task state.

Use `task-session` only when the user asks to start a runtime for the task.
