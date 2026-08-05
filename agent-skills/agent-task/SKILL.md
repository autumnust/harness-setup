---
name: agent-task
description: Initialize, operate, discover, and summarize portable filesystem-backed task workspaces. Use when the user asks to start or organize a personal or professional task in an agent-ready folder, resume work from such a folder, list agent tasks, report their status, or prepare task data for a board view.
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

- `status`: use `active`, `blocked`, `waiting`, `paused`, `done`, or `archived`;
- `updated`: set to the current `YYYY-MM-DD` when status or summary changes;
- `title`: keep human-readable; preserve `id` as the stable identity.

Update the prose under `Current state` and `Immediate next task` with concise,
current summaries. Do not duplicate detailed task lists in the front matter.

## Discover workspaces

Scan the roots named by the user. If none are named, scan `~/Documents`:

```bash
python3 <skill-dir>/scripts/discover_tasks.py <root> [<root> ...]
```

Use `--format json` when another tool or board will consume the result. The JSON
contains `schema_version`, scan roots, generation time, and task records with
identity, status, summaries, and absolute paths. It is an interchange format,
not a second source of truth; regenerate it from the filesystem instead of
maintaining a central cache.

When reporting tasks to the user, group or sort them by actionable state:
blocked first, then active, waiting, paused, done, and archived. Surface stale
or missing metadata as an unknown rather than inventing it.
