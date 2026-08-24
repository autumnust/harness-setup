---
name: task-session
description: Start or reuse tmux for an existing task, expose its TSS target, and record explicit active, paused, waiting, blocked, done, or cancelled state. Use when a task runtime should be reachable, its lifecycle should change, or it should later be cleaned through TSS; do not create the task folder or repository worktrees.
---

# Task Session

Attach runtime state to a task folder without creating another task record.
The task folder remains authoritative; tmux stores only enough identifying
metadata for runtime inspection. TSS discovers the resulting tmux session
without receiving a separate registration request.

## Start a session

1. Resolve the existing task directory from its filesystem record. For an
   `agent-task`, use its task folder. For an `agent-workspace` task, use its
   execution folder and resolve the current host's workspace root. Do not
   require tmux metadata to find the task.
2. Resolve the TSS host label from the request or from
   `$AGENT_HARNESS_HOME/config.json` at `task_runtime.tss.host_alias`, defaulting
   `AGENT_HARNESS_HOME` to `~/.agent-harness`. Ask for the label when neither
   source provides it. The coordinator may offer to save the confirmed label as
   this machine's default.
3. Resolve the session name, defaulting to a filesystem-safe form of the task
   name. If another task already uses that session name, ask for another name.
4. Run the bundled helper:

   ```bash
   python3 <skill-dir>/scripts/start_task_session.py \
     --task-dir "/path/to/task" \
     --workspace "/path/to/workspace" \
     --tss-host "<host-label>" \
     --session-name "<session-name>"
   ```

Omit `--workspace` for an `agent-task`. The helper starts workspace tasks in the
workspace root and general tasks in their task folder. It adds runtime references
as tmux custom options, records the host and session association in the task
README front matter, and prints `tss <host>:<session>`. Repeating the command is
safe when that session already belongs to the same task.

Do not edit TSS configuration, create repository worktrees, or create a second
task directory. Tack reporting is not implemented yet.

## Change lifecycle state

Use this workflow only after explicit human intent to pause, wait, block,
resume, finish, or cancel a task. Do not infer state from a missing session or
from the user ending a conversation.

For `active`, `paused`, `waiting`, or `blocked`, collect a short current-state
summary and one concrete next step or resume trigger, then run:

```bash
python3 <skill-dir>/scripts/set_task_state.py \
  --task-dir "/path/to/task" \
  --status waiting \
  --summary "Waiting for benchmark capacity." \
  --next-step "Resume when the GPU reservation is available."
```

Use `active` for an explicit resume. The helper atomically updates the task
file, removes a prior completion timestamp when resuming, and mirrors the new
state plus change time into the recorded tmux session when it exists.

For `done` or `cancelled`, use the finish workflow below. These terminal states
write `@agent_task_finished_at`; that field is the cleanup marker required by
`tss prune --finished`.

## Finish a task

Use this workflow when the user says `finish-task [<task-name>]` or asks to mark
the current task complete.

1. Resolve the task folder from the current directory, the explicit task name,
   or the workspace task discovery flow. Summarize the completed outcome. For
   full work, close the coordinator-owned execution records first.
2. Run the bundled compatibility helper:

   ```bash
   python3 <skill-dir>/scripts/finish_task.py \
     --task-dir "/path/to/task" \
     --outcome "<completed outcome>"
   ```

   Use `--status cancelled` only when the user intentionally closes incomplete
   work. The helper updates the task README before marking the tmux session with
   `@agent_task_status` and `@agent_task_finished_at`.
3. Leave the session running. Report whether its cleanup marker was written and
   explain that `tss prune --finished` can remove it after detachment. If the
   session is already missing, the completed filesystem state still succeeds;
   report the cleanup warning without reverting completion.

Do not infer completion from a missing session. A stopped tmux process may mean
a reboot, failure, or manual cleanup rather than a completed task.
