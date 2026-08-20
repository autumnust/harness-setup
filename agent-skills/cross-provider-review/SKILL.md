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
OpenAI Codex plugin and invokes its read-only adversarial-review runtime. Pass
the Coordinator's review context: the goal, user decisions, relevant design
links, repository guidance, and target diff. The plugin's `/codex:review`
command does not accept custom focus text, so the helper uses the companion
runtime that does.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/invoke_review.py --caller claude --scope branch --base <ref> --context '<review context>'
```

## Codex caller

Run the installed portable skill helper with `--caller codex`. It launches a
read-only Claude Code review with the current `opus` alias and `max` effort.
Pass the Coordinator's review context: the goal, user decisions, relevant
design links, repository guidance, and target diff.

```bash
python3 "${AGENT_SKILLS_DIR:-$HOME/.agents/skills}/cross-provider-review/scripts/invoke_review.py" --caller codex --scope branch --base <ref> --context '<review context>'
```

Use `--scope working-tree` when reviewing local changes without a base branch.
Return the external review output with its provider, model, effort, and command
status. That opinion is the review result. Do not edit files or apply findings.
