---
name: broadcast-harness
description: Push this harness-setup repo to SSH-reachable machines and run the installer (--update) on each, so their global Claude Code config matches this repo. Use when the user wants to roll out harness changes to remote development machines or "update all my machines". Only for this repo's own deployment — not general remote command execution.
---

# Broadcast the harness to remote machines

Rolls out the current `harness-setup` checkout to one or more ssh-reachable
hosts: rsyncs the working tree to each, then runs `install.sh --update` there
(diff + back up + no-op-when-synced). The remote needs no git or GitHub access.

All work is done by `scripts/broadcast.sh`. Targets come from named `Host`
entries in `~/.ssh/config`. `github.com` and wildcard patterns are never
targets.

## Procedure

1. **Enumerate candidates** — run `scripts/broadcast.sh --list` to get the host
   list. Do not assume the list; read it fresh each time.
2. **Let the user choose** — present the candidates and ask which to update
   (this is interactive-select-each-run by design). Accept "all" → pass `--all`.
   Never broadcast to hosts the user did not pick.
3. **Dry run first when unsure** — for an unfamiliar set, run with `--check` to
   confirm reachability and show the itemized rsync delta without writing
   anything. Show the user the per-host result.
4. **Deploy** — run `scripts/broadcast.sh HOST...` (or `--all`). It is
   sequential, preflights each host's reachability, and prints a pass/fail
   summary at the end.
5. **Report** — relay the summary. For any host that failed, say why
   (unreachable / rsync / install) — don't bury it.

## Notes & safety

- This writes to each remote's `~/` (`~/AGENTS.md`, `~/.claude/settings.json`,
  skills). The remote `install.sh --update` backs up anything it changes to
  `<path>.bak.<timestamp>`, so it is recoverable, but it is still a real change
  on another machine — confirm the target list before a non-`--check` run.
- Remote checkout path defaults to `~/harness-setup`; override with the
  `REMOTE_DIR` env var if needed.
- A host may be **unreachable** because it is offline. That is a skip, not a
  failure of the skill; report it to the user.
- After a successful update, the remote should restart Claude Code to pick up
  the new `settings.json`. Mention this.

## Examples

```bash
scripts/broadcast.sh --list                 # what can I reach?
scripts/broadcast.sh --check build-box       # preflight one host, write nothing
scripts/broadcast.sh build-box test-box      # deploy to two hosts
scripts/broadcast.sh --all                   # deploy to every candidate
```
