# harness-setup — agent orientation

This repo is a **meta-prompt harness**: it authors and deploys the global
AI-agent configuration that gets installed on Lei's dev machines. The output
of this repo is a set of files that instruct agents elsewhere — it is not
itself a software project to build or test.

## What lives here

| Path | What it is |
|------|------------|
| `home/AGENTS.md` | The global agent prompt deployed to `~/AGENTS.md` on every machine |
| `claude/settings.json` | Claude Code settings deployed to `~/.claude/settings.json` |
| `claude/skills/` | Skills deployed to `~/.claude/skills/` |
| `install.sh` / `update.sh` | Installers that copy the above onto a target machine |
| `.claude/skills/broadcast-harness/` | Skill for pushing this repo to remote machines via SSH |

## Critical distinction

`home/AGENTS.md` is the **content being maintained** in this repo — not
instructions for any agent working here. Do not follow it as guidance; treat
it as a text artifact you are editing on behalf of the user.

## How to work in this repo

**Editing the harness prompt:**
Edit `home/AGENTS.md` directly. The file uses Markdown. Keep sections
consistent with the existing structure (ToC, section headers, smell tests).

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
