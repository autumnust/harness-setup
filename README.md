# harness-setup — portable AI coding-agent harness

A self-contained **global** AI coding-agent harness that can be installed for
any developer. It has these layers:

- **Tool-agnostic core — `~/AGENTS.md`.** How any agent should communicate and
  work with the human user: explanation style, word choice, execution
  conventions.
  `AGENTS.md` is a cross-tool convention, not a Claude Code feature — the
  guidance is about *how to work with the human user*, so any coding agent that reads
  `AGENTS.md` can use it. This is the portable heart of the setup.
- **Skills — `agent-skills/`.** Reusable, invokable procedures (a directory
  per skill holding `SKILL.md`). Claude Code and Codex CLI both use this same
  convention, so `install.sh` installs each skill into `~/.claude/skills/`
  always, and into `~/.agents/skills/` plus the legacy-compatible
  `~/.codex/skills/` whenever Codex CLI is already present.
- **Agent workflows — `agent-workflows/`.** Provider-neutral role prompts,
  topology, handoff contracts, model policies, and workflow procedures.
  Installation renders these into native Claude Markdown agents and Codex TOML
  agents, while keeping one readable source of truth.
- **Claude Code integration — `~/.claude/settings.json`, plugins.** Wires the
  core into Claude Code specifically: statusline, enabled plugins, and a
  `~/.claude/CLAUDE.md` symlink pointing at `~/AGENTS.md`.

Drop this onto a new device and run `install.sh` to restore the global setup.

## Filesystem agent tasks

The installed `agent-task` skill creates portable workspaces for personal or
professional tasks, starts a TSS-reachable tmux session, and discovers their
current state directly from the filesystem. Ask an agent, for example:

> Initialize an agent task for organizing my personal finances.

The agent resolves a name, objective, destination, TSS host label, and session
name with you, then hydrates a workspace containing raw inputs, stable context,
decisions, task tracking, working artifacts, and final outputs. It starts tmux
in that task folder and returns `tss <host>:<session>`. The tmux custom options
make the task available to a TSS metadata reader without a separate
registration request. There is no user-facing command to remember; the
deterministic scripts are internal skill resources.

Each workspace keeps small discovery metadata in `README.md`, including a
stable ID, status, and update date. Ask "show me all my agent tasks" to scan
one or more filesystem roots and summarize them. The scanner can also emit
versioned JSON with paths, statuses, objectives, current state, and immediate
next tasks, providing a future task-board integration point without adding a
database or cached index. The workspace files remain authoritative.

For multi-repository development environments, the installed `agent-workspace`
skill creates a versioned workspace root, clones the selected repositories,
and prepares separate Git worktree containers for isolated changes. From an
initialized workspace, ask `start-task <task-name>` to create a structured
execution folder under the configured execution root and start a tmux session
that TSS can discover. The session opens in the workspace root. Generated output
goes to the task's execution folder unless the user asks otherwise. Durable
material enters `context/` only when the user explicitly requests it. Ask
`list-tasks` to find task records associated with the workspace without
requiring tmux, including folders created at an explicitly overridden location.
Repository worktrees remain a later per-repository operation. The richer
long-running-work structure is created only when the coordinator selects that
workflow. Its committed source is
`agent-skills/agent-workspace/`; the copies installed under the supported agent
runtime directories are generated outputs.

New workspace manifests carry a stable ID so the workspace can be rehydrated at
a different absolute path on another host. Rehydration asks for the exact
destination and validates existing workspace metadata, repository origins, and
primary branches before cloning missing repositories.

The shared `task-session` skill can restore a TSS-reachable tmux session for an
existing `agent-task` folder. In that case the task folder is reused as the
working directory and no execution folder is added.

From either task type, explicit requests to pause, wait, block, resume, finish,
or cancel update the filesystem task record and then mirror that state into
tmux when its session exists. TSS displays the recorded task state, and
`tss prune --finished` removes only detached sessions carrying a task ID,
terminal state, and completion timestamp. From an initialized professional
workspace, ask `list active tasks` to filter its filesystem records to
`status: active`.

> Project-local skills and project `AGENTS.md` files are **not** included here;
> they belong in their respective project repositories.

## Quick start on a new device

```bash
git clone git@github.com:autumnust/harness-setup.git ~/Documents/harness-setup
cd ~/Documents/harness-setup
./install.sh
```

TSS is an optional companion dependency. It is not fetched by a normal
installation. To install the revision recorded in
[`dependencies/tss.json`](dependencies/tss.json), run:

```bash
./install.sh --with-tss
```

The installer stores the checked-out source at
`~/.agent-harness/dependencies/tss` and installs its command at `~/bin/tss`.
Use `./update.sh --with-tss` to refresh it to the revision currently recorded
by the harness. This requires Git and network access; an installation without
this option remains usable, but task sessions cannot be opened with the `tss`
command until TSS is installed.

On a **fresh device** with no existing harness instructions, settings, skills,
workflow specs, or generated agents, this installs cleanly with no prompts.

To add a machine-specific paragraph to the deployed `~/AGENTS.md`, select a
profile once:

```bash
./install.sh --instance example-workstation
```

Profiles live in `instances/<name>.md`. Updates and rollback reuse the selected
profile; `--no-instance` returns the machine to the portable instructions only.

On a **device that already has global agent config**, `./install.sh` **refuses
to overwrite anything**. It lists every conflicting file and exits non-zero.
Pick one of:

```bash
./install.sh --backup         # Safest. Move each conflict to
                              #   <path>.bak.<timestamp> before installing.
./install.sh --overwrite      # Replace existing files outright. No backup.
./install.sh --skip-existing  # Keep existing files; only install missing ones.
./install.sh --update         # Steady-state sync: rewrite only files that
                              #   differ, diff + back up each first, no-op
                              #   when in sync. Use update.sh below instead.
```

### Prompt to paste into Claude Code on the new device

> Clone `git@github.com:autumnust/harness-setup.git` into `~/Documents/harness-setup`, then run
> `./install.sh` from inside it.
>
> If the script detects existing global agent config and exits
> with a conflict list, **ask me** which mode I want — `--backup`,
> `--overwrite`, or `--skip-existing` — before re-running. Do not
> choose for me.
>
> After the install succeeds, verify the enabled plugins listed in
> `~/.claude/settings.json` are installed by checking
> `~/.claude/plugins/installed_plugins.json`. Report anything that
> needed manual intervention.

## What gets installed

| Source in this repo | Target on the new machine |
|---|---|
| `home/AGENTS.md` | `~/AGENTS.md` (and tool-specific global-instruction symlinks for Claude and Codex) |
| `instances/<name>.md` | Appended to `~/AGENTS.md` only when that profile is selected |
| `claude/settings.json` | `~/.claude/settings.json` (with `node` path repatched) |
| `agent-skills/<name>/` | `~/.claude/skills/<name>/`; also `~/.agents/skills/<name>/` and `~/.codex/skills/<name>/` when Codex is present |
| `agent-workflows/` | `~/.agent-harness/specs/` plus rendered `~/.claude/agents/agent-harness/*.md` and, when Codex is present, `~/.codex/agents/agent-harness-*.toml` |
| coordinator model and workflow depth | Codex Terra or Claude Code Sonnet plus medium effort; `agents.max_depth = 2` merged into Codex config |
| mutable runtime configuration | `~/.agent-harness/config.json` (initialized once, confirmed and maintained by the coordinator) |
| versioned harness releases | `~/.agent-harness/releases/<release-id>/` with `~/.agent-harness/current` selecting the active release |
| mutable learner state | `~/.agent-harness/state/learner-profiles/` (initialized once, never overwritten by updates or rollback) |

## Portable agent workflow

The main session is the coordinator. Fast is the default path: the
coordinator implements directly or fans out Executors. Education runs on
that path. Full-path prepper, review, and PR maintenance are escalation.
Nesting stops after two subagent levels.

```mermaid
flowchart TB
    Human["Human user"] <-->|default interface| Coordinator["Coordinator<br/>root session and education mode"]
    Executor["Executor<br/>worktree, high effort"]
    Coordinator -->|fast: 0-N disjoint scopes| Executor

    Prep["Environment Prepper"]
    Reviewer["Reviewer<br/>other-foundation opinion"]
    Maintainer["PR Maintainer"]
    Coordinator -->|full: long-running| Prep
    Coordinator -->|full: review| Reviewer
    Coordinator -->|full: PR work| Maintainer
    Reviewer -->|invoke and wait| Opinion(["Cross-provider opinion"])
    Opinion -->|findings| Reviewer
    Reviewer -->|return opinion| Coordinator
    Maintainer -.->|registered PR only| Executor

    Coordinator -.->|invoke| Retrospector(["Retrospector skill"])
```

Only the coordinator spawns agents, writes canonical state, or invokes the
`retrospector` skill. The Mermaid diagram is a summary; ordinary-work and
education behavior is defined in the
[Coordinator prompt](./agent-workflows/roles/coordinator.md). The shared
[PR-maintenance](./agent-workflows/workflows/pr-maintenance.md) and
[PR-review](./agent-workflows/workflows/pr-review.md) workflows define their
respective ordered processes.
The provider limit remains depth two as a defensive ceiling even though the
current topology uses only depth-one leaves. See
[`agent-workflows/`](./agent-workflows/) for the complete contracts and routing
rules and the [detailed topology](./agent-workflows/topology.md).

## What the settings.json controls

```jsonc
{
  "statusLine": { ... claude-hud node command ... },
  "enabledPlugins": {
    "claude-hud@claude-hud": true,
    "understand-anything@understand-anything": true,
    "frontend-design@claude-plugins-official": true,
    "crit@crit": true
  },
  "extraKnownMarketplaces": { ... github sources for each ... },
  "model": "sonnet",
  "effortLevel": "medium",
  "skipDangerousModePermissionPrompt": true,
  "agentPushNotifEnabled": true
}
```

Plugins are not vendored here. The marketplace entries tell Claude Code
where to fetch them on first launch — they auto-install into
`~/.claude/plugins/cache/` on the new device. The OpenAI Codex plugin supplies
the read-only adversarial-review runtime used by Reviewer in Claude Code
sessions.

## Idempotency

Re-running `install.sh` is safe: the default mode refuses conflicts, while
`--backup` and `--update` preserve replaced content as
`<path>.bak.<timestamp>`. Mutable state is never replaced.

Each successful install also preserves an immutable source snapshot. Repeating
an install with identical content reuses its release ID instead of creating a
duplicate.

```bash
~/.agent-harness/bin/harness-release list
~/.agent-harness/bin/harness-release current
~/.agent-harness/bin/harness-release rollback <release-id>
```

Rollback reruns the selected release's installer, then changes `current` after
that installation succeeds. Runtime configuration, learner profiles, PR
queues, and execution history remain outside release snapshots.

## What is deliberately not included

- `~/.claude/projects/`, `sessions/`, `tasks/`, `plans/`, `file-history/`,
  `telemetry/`, `cache/`, `backups/`, `paste-cache/`, `debug/`,
  `history.jsonl` — per-session state, not portable config.
- `~/.claude/plugins/cache/` — re-fetched from marketplaces.
- MCP server auth tokens for claude.ai-bridge integrations (Slack,
  Gmail, Notion, Figma, …) — those re-authenticate interactively on
  first use of each.
- Project-level `AGENTS.md` files and project `.claude/` directories.
- Mutable runtime configuration, learner profiles, PR queues, and execution
  history. The installer initializes local configuration and state directories
  but never checks their contents into this repository or overwrites them during
  updates.

## License

This project is licensed under the [MIT License](./LICENSE). The vendored
`frontend-slides` skill retains its own [MIT license](./agent-skills/frontend-slides/LICENSE).

## Keeping a machine in sync after the repo changes (repo → `~/`)

The repo is the source of truth. After it changes — you edited `home/AGENTS.md`
and pushed, or you pulled someone else's commit — the live `~/` copy is stale,
because `install.sh` installs by **copying** (it won't silently overwrite). To
push the latest repo state onto the current machine:

```bash
cd ~/Documents/harness-setup
./update.sh            # git pull --ff-only, then install.sh --update
./update.sh --no-pull  # skip the pull (you just edited the repo locally)
```

`update.sh` only rewrites files that actually differ, prints a diff of each
change, backs up the prior copy to `<path>.bak.<timestamp>`, and is a no-op
when everything is already in sync. Restart active Claude Code and Codex
sessions afterward so they re-read the refreshed global config.

## Testing deployment without touching the live harness

On macOS, run the same fail-closed Seatbelt smoke test used by CI:

```bash
scripts/smoke-test-deployment.sh --offline
```

It installs into a temporary home, denies network and all writes outside that
temporary root, launches both real CLIs, verifies the rendered workflow and
update behavior, then cleans up. See
[`tests/deployment-smoke/README.md`](./tests/deployment-smoke/README.md) for the
coverage, containment boundary, CI trigger, and optional online awareness probe.

## Updating the repo from a source machine (`~/` → repo)

The other direction: you tweaked the live global config and want to capture it
back into the repo before committing.

```bash
cd ~/Documents/harness-setup
cp ~/AGENTS.md home/AGENTS.md
cp ~/.claude/settings.json claude/settings.json
rsync -a --delete --exclude='.git' ~/.claude/skills/ agent-skills/
git add -A && git commit -m "sync global config" && git push
```

Skills now deploy to three possible live locations (`~/.claude/skills/` and,
if Codex CLI is present, `~/.agents/skills/` and `~/.codex/skills/`). Prefer
editing `agent-skills/` in the repo directly and re-running `./update.sh`
rather than live-editing a deployed copy — if you do live-edit one, rsync from
*that* one back into `agent-skills/`, not several copies, or you risk
overwriting one tool's edits with another's.
