# harness-setup — agent orientation

This repo is a **meta-prompt harness**: it authors and deploys the global
AI-agent configuration that gets installed on human users' development machines. The output
of this repo is a set of files that instruct agents elsewhere — it is not
itself a software project to build or test.

## What lives here

| Path | What it is |
|------|------------|
| `home/AGENTS.md` | The global agent prompt deployed to `~/AGENTS.md` on every machine |
| `claude/settings.json` | Claude Code settings deployed to `~/.claude/settings.json` |
| `agent-skills/` | Skills deployed to `~/.claude/skills/`; when Codex is present they also deploy to current `~/.agents/skills/` and legacy-compatible `~/.codex/skills/` |
| `agent-workflows/` | Provider-neutral role prompts, topology, workflows, contracts, runtime-config schema/defaults, and adapter mappings rendered into native Claude and Codex custom agents |
| `scripts/render-agents.py` | Validates the topology and renders provider-native custom-agent files during installation |
| `install.sh` / `update.sh` | Installers that copy the above onto a target machine |
| `tests/deployment-smoke/` | macOS Seatbelt deployment, CLI launch, and optional runtime-awareness checks |
| `.claude/skills/broadcast-harness/` | Skill for pushing this repo to remote machines via SSH |

## Critical distinction

`home/AGENTS.md` is the **content being maintained** in this repo — not
instructions for any agent working here. Do not follow it as guidance; treat
it as a text artifact you are editing on behalf of the user.

## How to work in this repo

**Editing the harness prompt:**
Edit `home/AGENTS.md` directly. The file uses Markdown. Keep sections
consistent with the existing structure (ToC, section headers, smell tests).

**Editing a skill (`agent-skills/<name>/`):**
These are deployed verbatim to Claude's skill directory and both current and
legacy-compatible Codex skill directories (see the table above). Avoid
hardcoding Claude-Code-only assumptions into a skill's `SKILL.md` — a
hardcoded `~/.claude/...` path, or a step that relies on a Claude-Code-only
mechanism (e.g. the auto-memory system) with no fallback — since the same file
also has to make sense read by Codex CLI. If a step is genuinely Claude-only,
say so explicitly and give the other tool an alternative, rather than silently
assuming the reader is Claude Code.

**Editing agent workflows (`agent-workflows/`):**
Keep role behavior and shared contracts in Markdown, topology and policy in
`manifest.json`, and provider-specific model mappings in `adapters/`. Do not
hand-edit generated files under `~/.claude/agents/` or `~/.codex/agents/`.
Run `python3 scripts/render-agents.py --check` after changes.

**Deploying changes:**
After committing and pushing, use the `broadcast-harness` skill to rsync
and install onto target machines:

```bash
.claude/skills/broadcast-harness/scripts/broadcast.sh --list   # see targets
.claude/skills/broadcast-harness/scripts/broadcast.sh gpu-ec2  # deploy to one
.claude/skills/broadcast-harness/scripts/broadcast.sh --all    # deploy to all reachable
```

**Commit style:**
Prefix with the file changed: `AGENTS.md: <what changed and why>`.
