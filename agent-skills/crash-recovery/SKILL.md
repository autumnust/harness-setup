---
name: crash-recovery
description: Recover the task-to-workspace map after a reboot or lost tmux server, and optionally verify recorded TSS sessions without attaching to them.
---

# Crash Recovery

Use this skill when a reboot, terminal failure, or lost tmux server leaves the
human user unsure which workspace and task belong to a former session. The
filesystem task record is the source of truth. tmux only confirms whether a
recorded session is currently available.

## Report task records

Run the bundled report without `--validate-tss` first. It reads the configured
execution root from `$AGENT_HARNESS_HOME/config.json`, defaulting
`AGENT_HARNESS_HOME` to `~/.agent-harness`:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py
```

The report lists each task's status, execution folder, workspace folder when
one is recorded, and its saved `host:session` TSS target. It does not create,
resume, attach to, rename, or remove any session.

For an execution root that is not configured on this machine, pass it
explicitly:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py \
  --execution-root "/absolute/path/to/execution-notes"
```

## Verify recorded TSS sessions

Only when the human user asks to validate live availability, add
`--validate-tss`:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py --validate-tss
```

It runs `tss <host>` once for every recorded host and adds a `TSS state`
column: `present`, `missing`, or `unknown`. This does not attach to a session,
but scanning a remote host can refresh its authentication. Report that fact if
it occurs.

## Recreate a missing task session

After the human user identifies a missing non-terminal task, recreate only the
named task using its recorded workspace, host, and session name:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py \
  --recreate --task "review_context_api_plumbing"
```

This starts a new detached tmux session through the `task-session` helper, so
the session is again visible through `tss <host>`. It restores the working
directory and task metadata, not the former tmux processes, pane contents, or
Codex process. The command refuses `done`, `cancelled`, and `archived` tasks,
requires an explicit task name, and will not take over a tmux session belonging
to a different task.

## Codex conversations

Task records do not currently store a Codex conversation identifier. To find
a candidate conversation, search `~/.codex/sessions/` for records whose
`session_meta.cwd` equals the task's workspace path, then confirm the task name
or a task-specific action in the conversation. Treat that as an evidence-based
association, not proof that it occupied a particular tmux pane.

Do not recreate a replacement tmux session or resume Codex unless the human
user explicitly asks. A rebooted local tmux server cannot restore its old
processes or pane buffers when no tmux-resurrect save exists.
