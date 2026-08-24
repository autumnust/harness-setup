---
name: agent-task
description: Initialize, operate, discover, summarize, start TSS-reachable tmux sessions, and record explicit pause, wait, block, resume, finish, or cancel state for portable filesystem-backed task workspaces. Use for personal or professional task folders that are not multi-repository development workspaces.
---

# Agent Task

Use the filesystem as the canonical task record. Keep raw inputs, stable context,
decisions, work in progress, and deliverables inspectable without chat history.

## Initialize a workspace

1. Resolve the task name, objective, and destination from the request.
2. If the destination is missing, ask where to create the workspace and offer
   `~/Documents` as the default. Ask nothing else unless an unresolved choice
   would materially change the result.
3. Run the bundled hydrator, resolving `<skill-dir>` to this skill's directory:

   ```bash
   python3 <skill-dir>/scripts/hydrate_task.py \
     --name "<folder name>" \
     --objective "<objective>" \
     --destination "<existing parent directory>"
   ```

4. Read the generated `README.md`, `tasks.md`, `AGENTS.md`, and relevant
   context before beginning work.

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

## Start a task session

When the user wants to work on an agent task through tmux or TSS, use the task
folder itself as the working directory. Do not create a second execution folder.
Resolve the TSS host label and session name together, then use the installed
`task-session` skill. The resulting `runtime_host` and `tmux_session` fields are
discoverable task metadata; tmux determines whether the session is currently
running.

## Discover workspaces

Scan the roots named by the user. If none are named, scan `~/Documents`:

```bash
python3 <skill-dir>/scripts/discover_tasks.py <root> [<root> ...]
```

Use `--format json` when another tool or board will consume the result. The JSON
contains `schema_version`, scan roots, generation time, and task records with
identity, status, summaries, absolute paths, and any recorded tmux/TSS
association. It is an interchange format, not a second source of truth;
regenerate it from the filesystem instead of maintaining a central cache.

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
