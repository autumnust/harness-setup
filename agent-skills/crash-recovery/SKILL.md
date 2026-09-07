---
name: crash-recovery
description: Recover the task-to-workspace map after a reboot or lost tmux server, and optionally verify recorded TSS sessions without attaching to them.
---

# Crash Recovery

The task folder and catalog survive a lost tmux server. tmux only reports
whether a recorded session is currently available.

## Find prior work

Start with the local catalog:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/task-catalog" list \
  --format json
```

If a manual copy, move, or old installation is missing, repair registration
before listing again:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/task-catalog" reconcile \
  <root> [<root> ...] --format json
```

For a report that also resolves local workspace paths, run:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py --format json
```

These commands do not contact TSS or create, attach to, rename, or remove a
session. Use `-H` with `task-catalog list` only for direct human terminal use.

## Check or recreate sessions

Only after the user asks for live validation, run:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py \
  --validate-tss --format json
```

This contacts each recorded host without attaching and may refresh remote
authentication; report when that occurs. To recreate one missing, nonterminal
session after the user selects it:

```bash
python3 <skill-dir>/scripts/recover_task_sessions.py \
  --recreate --task "<task-name>" --format json
```

Recreation restores the working directory and metadata, not old processes,
panes, buffers, or the prior agent process. It refuses finished, cancelled, and
archived tasks and never takes over another task's session.

Task records do not store an agent conversation ID. A matching working
directory in `~/.codex/sessions/` is evidence of a possible conversation, not
proof that it occupied a particular tmux pane. Do not recreate a session or
resume an agent process without an explicit request.
