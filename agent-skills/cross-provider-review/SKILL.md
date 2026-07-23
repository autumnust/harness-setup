---
name: cross-provider-review
description: Invoke the independent review provider selected for the current harness. Use only from the Reviewer role.
user-invocable: false
allowed-tools: Bash(python3 *)
---

# Cross-provider review

Only the harness Reviewer role may use this skill. It invokes exactly one
read-only opinion from the model foundation different from the active
coordinator and executor, and waits for that opinion to finish.

## Claude Code caller

Run the bundled helper with `--caller claude`. It discovers the installed
OpenAI Codex plugin and invokes its native `review` runtime. The plugin's
`/codex:review` command disables automatic model invocation, so the helper calls
the same companion runtime directly rather than claiming the Reviewer can issue
a user-only slash command.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/invoke_review.py --caller claude --scope branch --base <ref>
```

## Codex caller

Run the installed portable skill helper with `--caller codex`. It launches a
read-only Claude Code review with the current `opus` alias and `max` effort.

```bash
python3 "${AGENT_SKILLS_DIR:-$HOME/.agents/skills}/cross-provider-review/scripts/invoke_review.py" --caller codex --scope branch --base <ref>
```

Use `--scope working-tree` when reviewing local changes without a base branch.
Return the external review output with its provider, model, effort, and command
status. Treat it as evidence for the Reviewer's later adversarial judgment. Do
not edit files or apply findings.
