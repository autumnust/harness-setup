---
name: task-session
description: Route an explicit task runtime request to TSS or an explicit task lifecycle request to agent-task. Use for compatibility with task-session wording; it does not own tasks or runtime state.
---

# Task session compatibility router

Resolve the task with `task-catalog list --format json`. Ask when several local
paths match.

For a runtime request, collect the required TSS target, agent command, and the
task path on that host, then run:

```bash
tss start <host>:<session> \
  --cwd "<task-folder-on-target-host>" \
  --meta task_id=<task-id> \
  --meta task_kind=<agent-task-or-workspace-task> \
  -- <agent-command> [args...]
```

The target is required; do not restore old host defaults. The runtime starts in
the task folder for both general and workspace tasks. TSS owns the session, and
starting or stopping it does not change task status.

For an explicit lifecycle request, use:

```bash
agent-task set-state \
  --task-dir "<task-folder>" \
  --status <status> \
  --summary "<current state or outcome>" \
  [--next-step "<next action or resume trigger>"] \
  --format json
```

Nonterminal states require a next step. Never infer a task-state change from a
runtime disconnect or failure.
