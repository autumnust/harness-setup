# harness-setup — Lei's portable Claude Code global config

A self-contained snapshot of my **global** Claude Code harness setup
(`~/AGENTS.md`, `~/.claude/settings.json`, `~/.claude/skills/`, plus a
clone of `kumo-skills-catalog`). Drop this onto a new device, run
`install.sh`, and the global half of my CC environment is restored.

> Project-local skills (`bench-ec2`, `gpu-ec2`, `learn`, `ship`, `cs224w`,
> `pdf`) and project `AGENTS.md` files are **not** included here — those
> live inside their respective project repos.

## Quick start on a new device

```bash
git clone git@github.com:autumnust/harness-setup.git ~/Documents/harness-setup
cd ~/Documents/harness-setup
./install.sh
```

On a **fresh device** with no existing `~/AGENTS.md`, `~/.claude/settings.json`,
or `~/.claude/skills/*`, this installs cleanly with no prompts.

On a **device that already has global Claude Code config**, `./install.sh`
**refuses to overwrite anything**. It lists every conflicting file and
exits non-zero. Pick one of:

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
> If the script detects existing global Claude Code config and exits
> with a conflict list, **ask me** which mode I want — `--backup`,
> `--overwrite`, or `--skip-existing` — before re-running. Do not
> choose for me.
>
> After the install succeeds, verify the four plugins listed in
> `~/.claude/settings.json` are installed by checking
> `~/.claude/plugins/installed_plugins.json`. Report anything that
> needed manual intervention.

## What gets installed

| Source in this repo | Target on the new machine |
|---|---|
| `home/AGENTS.md` | `~/AGENTS.md` (and `~/.claude/CLAUDE.md` → symlink to it) |
| `claude/settings.json` | `~/.claude/settings.json` (with `node` path repatched) |
| `claude/skills/frontend-slides/` | `~/.claude/skills/frontend-slides/` |
| *(cloned at install)* | `~/Documents/kumo-skills-catalog/` (from `kumo-ai/kumo-skills-catalog`) |

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
  "effortLevel": "xhigh",
  "skipDangerousModePermissionPrompt": true,
  "agentPushNotifEnabled": true
}
```

Plugins are not vendored here. The marketplace entries tell Claude Code
where to fetch them on first launch — they auto-install into
`~/.claude/plugins/cache/` on the new device.

## Idempotency

Re-running `install.sh` is safe. Any file it would overwrite is moved
aside to `<path>.bak.<timestamp>` first.

## What is deliberately not included

- `~/.claude/projects/`, `sessions/`, `tasks/`, `plans/`, `file-history/`,
  `telemetry/`, `cache/`, `backups/`, `paste-cache/`, `debug/`,
  `history.jsonl` — per-session state, not portable config.
- `~/.claude/plugins/cache/` — re-fetched from marketplaces.
- MCP server auth tokens for claude.ai-bridge integrations (Slack,
  Gmail, Notion, Figma, …) — those re-authenticate interactively on
  first use of each.
- Project-level `AGENTS.md` files and project `.claude/` directories.

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
when everything is already in sync. Restart Claude Code afterward so it
re-reads the refreshed global config.

## Updating the repo from a source machine (`~/` → repo)

The other direction: you tweaked the live global config and want to capture it
back into the repo before committing.

```bash
cd ~/Documents/harness-setup
cp ~/AGENTS.md home/AGENTS.md
cp ~/.claude/settings.json claude/settings.json
rsync -a --delete --exclude='.git' ~/.claude/skills/ claude/skills/
git add -A && git commit -m "sync global config" && git push
```
