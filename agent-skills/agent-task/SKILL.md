---
name: agent-task
description: Initialize, operate, discover, summarize, and run portable filesystem-backed task workspaces with TSS-reachable tmux sessions and explicit lifecycle state. Use for personal or professional task folders that are not multi-repository development workspaces.
---

# Agent Task

Use the task folder as the authoritative task record. Keep raw inputs, stable
context, decisions, work in progress, and deliverables inspectable without chat
history. The machine-local task catalog records where this host has the folder;
it does not replace the folder or its Git history.

## Initialize a workspace

1. Resolve the task name, objective, destination, TSS host label, and tmux
   session name together. The default session name is a filesystem-safe form of
   the task name. Resolve the host label from the request or from
   `$AGENT_HARNESS_HOME/config.json` at `task_runtime.tss.host_alias`, defaulting
   `AGENT_HARNESS_HOME` to `~/.agent-harness`. If the destination or host label
   is missing, ask for all missing values together; offer `~/Documents` for the
   destination and offer to save a confirmed host label as this machine's
   default.
2. Run the installed CLI. It creates the folder, registers it, and starts its
   tmux session as one scripted operation:

   ```bash
   "${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" init \
     --name "<folder name>" \
     --objective "<objective>" \
     --destination "<existing parent directory>" \
     --tss-host "<host-label>" \
     --session-name "<session-name>" \
     --format json
   ```

   Default `AGENT_HARNESS_HOME` to `~/.agent-harness` when constructing this
   command. The CLI reads the configured TSS host when `--tss-host` is omitted;
   pass every resolved value explicitly when deterministic replay matters.

   The low-level hydrator creates the complete folder and then registers its path through
   `$AGENT_HARNESS_HOME/bin/task-catalog`, defaulting `AGENT_HARNESS_HOME` to
   `~/.agent-harness`. If catalog registration or session setup fails, the CLI
   returns a nonzero status and leaves the valid folder intact. Read its JSON
   fields to distinguish `catalog_registered` from `session_started`. Do not run
   `init` again against that path; run the failed operation directly.

   Session setup writes the task ID, task name, task kind, task path, status,
   and TSS host as tmux custom options. It also records the host and session in
   the task README and returns the `tss_target` value.
3. Read the generated `README.md`, `tasks.md`, `AGENTS.md`, and relevant
   context before beginning work. Return the task path and the TSS connection
   command.

The hydrator refuses to overwrite an existing path. Do not bypass that guard.

## Work in a workspace

Follow its `AGENTS.md`. Treat the `README.md` front matter as discoverable task
metadata and keep these fields current:

- `status`: use `active`, `blocked`, `waiting`, `paused`, `done`, `cancelled`,
  or `archived`;
- `updated`: set to the current `YYYY-MM-DD` when status or summary changes;
- `title`: keep human-readable; preserve `id` as the stable identity.

Update the prose under `Current state` and `Immediate next task` with concise,
current summaries. Do not duplicate detailed task lists in the front matter.

## Start or restore a task session

Initialization already starts a session. Use this workflow only to restore a
session that was not created by this version of the skill, or whose tmux session
was removed. Use the task folder itself as the working directory; do not create
a second execution folder. Resolve the TSS host label and session name together,
then use the installed `task-session` skill. The resulting `runtime_host` and
`tmux_session` fields are discoverable task metadata; tmux determines whether
the session is currently running.

## Discover workspaces

Query the machine-local catalog. With no roots, this lists every registered
general task on the current host. Named roots filter the catalog result by local
path; they do not start a filesystem scan:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" list \
  [<root> ...] --format json
```

Normal discovery always invokes the catalog's fixed agent-task list operation.
Use `--format json` when another tool or board will consume the result. The JSON
contains `schema_version`, catalog source, optional path filters, generation
time, and task records with identity, status, summaries, absolute paths, and
any recorded tmux/TSS association. Use `-H` or `--human` when a person will read
the terminal output; this prints one wrapped record at a time instead of a wide
Markdown table.

Manual clones, moves outside the skill, and older task folders may not yet be
registered. Repair registration explicitly by scanning only chosen roots:

```bash
"${AGENT_HARNESS_HOME:-$HOME/.agent-harness}/bin/agent-task" reconcile \
  <root> [<root> ...] --format json
```

Reconciliation reads folder metadata and updates the local catalog. It is a
repair or backfill action, not part of normal discovery.

When reporting tasks to the user, group or sort them by actionable state:
blocked first, then active, waiting, paused, done, cancelled, and archived.
Surface stale or missing metadata as an unknown rather than inventing it.

## Change task state

Only change lifecycle state after an explicit user request. A conversational
stopping point, missing tmux session, disconnection, or reboot is not a task
state change. For `paused`, `waiting`, `blocked`, or resumed `active` work,
collect a current-state summary and a concrete next step or resume trigger,
then use the installed `task-session` state workflow on the same task folder.
The task file is authoritative; tmux receives the same state when it exists.

## Finish a task

When the user says `finish-task` from an agent-task folder, summarize the
completed outcome and use the installed `task-session` finish workflow on that
same folder. The filesystem record is updated before the tmux session receives
its completion metadata. Leave the session running for inspection; TSS can
remove it later with `tss prune --finished`.
