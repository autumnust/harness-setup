---
name: task-session
description: Start or reuse tmux for an existing task, expose its TSS target, and record explicit active, paused, waiting, blocked, done, or cancelled state. Use when a task runtime should be reachable, its lifecycle should change, or it should later be cleaned through TSS; do not create the task folder or repository worktrees.
---

# Task Session

The task folder is authoritative. The catalog records local paths and session
data; tmux stores runtime metadata for TSS.

## Resolve the task

Use the installed commands in `${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin`:
`task-catalog list --format json`, `agent-task list --format json`, or
`agent-workspace list-tasks --workspace <path> --format json`. Do not scan
directories or require a live tmux session. Ask when several local locations
match one task.

## Start or restore a session

Resolve the existing task folder, optional workspace path, TSS host, and session
name, then run:

```bash
python3 <skill-dir>/scripts/start_task_session.py \
  --task-dir "/path/to/task" \
  --workspace "/path/to/workspace" \
  --tss-host "<host>" \
  --session-name "<session>" \
  --format json
```

Omit `--workspace` for a general task. Omit it for a workspace task only when
the catalog has one matching local workspace. The helper uses the configured
TSS host when available, starts in the correct folder, updates the task record
and catalog, and returns `tss <host>:<session>`. Repeating it is safe only when
the session already belongs to the same task.

## Change state

Run this only after an explicit request. For `active`, `paused`, `waiting`, or
`blocked`, collect a current-state summary and next step:

```bash
python3 <skill-dir>/scripts/set_task_state.py \
  --task-dir "/path/to/task" \
  --status waiting \
  --summary "<current-state>" \
  --next-step "<next-step-or-resume-trigger>" \
  --format json
```

Use `active` for an explicit resume. For `done` or `cancelled`, collect the
outcome. When the full workflow was used, close its coordinator-owned execution
records before running:

```bash
python3 <skill-dir>/scripts/finish_task.py \
  --task-dir "/path/to/task" \
  --outcome "<outcome>" \
  --format json
```

Add `--status cancelled` only for intentionally abandoned work. The helpers
write the task file before tmux and catalog state. A missing session or catalog
refresh failure is a warning and does not undo that file update.

Leave a finished session running for inspection. `tss prune --finished` may
remove it after detachment. Never infer a lifecycle change from a disconnect,
reboot, or missing session. Do not edit TSS configuration or create task
folders or repository worktrees from this skill.
