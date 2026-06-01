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

## Updating this repo from the source machine

If I add a new global skill or tweak settings before fully migrating:

```bash
cd ~/Documents/harness-setup
cp ~/AGENTS.md home/AGENTS.md
cp ~/.claude/settings.json claude/settings.json
rsync -a --delete --exclude='.git' ~/.claude/skills/ claude/skills/
git add -A && git commit -m "sync global config" && git push
```
