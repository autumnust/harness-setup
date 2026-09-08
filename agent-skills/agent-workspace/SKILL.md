---
name: agent-workspace
description: Create or rehydrate a portable multi-repository workspace, then create and discover its task contexts. Use only when the user explicitly chooses an agent workspace; edits spanning several repositories do not select this workflow by themselves.
---

# Agent workspace

An agent workspace is reusable multi-repository context. Each task has a
separate execution folder and lifecycle. Runtime sessions are optional.

## Create or rehydrate

Resolve and confirm the destination and repository definitions. Each `--repo`
value is `name|url|branch|role`; branch may be empty, and role is `active` or
`reference`.

```bash
agent-workspace init \
  --name "<workspace-name>" \
  --destination "<parent>" \
  --repo "<name>|<url>|<branch>|active" \
  --format json

agent-workspace rehydrate \
  --manifest "<workspace.yaml>" \
  --destination "<exact-path>" \
  --format json
```

The CLI validates destinations, repository origins, and primary branches. It
clones only missing repositories and registers the workspace. Preserve a
partially created folder and report the failed step. Read the resulting
`README.md`, `AGENTS.md`, and `workspace.yaml`.

## Create or find a task

```bash
agent-workspace start-task \
  --workspace "<workspace>" \
  --name "<task-name>" \
  --objective "<objective>" \
  [--execution-root "<parent>" | --execution-folder "<exact-path>"] \
  --format json

agent-workspace list-tasks \
  --workspace "<workspace>" \
  [--status <status>] \
  --format json
```

`start-task` creates and registers the task context. It does not start a coding
agent, TSS, or tmux. If no folder option is provided, it uses the configured
execution root. Read the returned folder's `README.md` and `AGENTS.md`. Use
`-H` for direct terminal reading.

Use `agent-task set-state` for explicit lifecycle changes. Use `task-session`
only when the user asks to start a runtime.

## Repository work

Write generated output to the task's execution folder. Add reusable workspace
material to `context/` only when requested. Before editing a nested repository,
create its task worktree under `<repository>-worktree/<task-name>/`; keep the
named checkout on its primary branch. Do not add nested repositories, task
worktrees, virtual environments, or generated caches to the workspace Git
index.
