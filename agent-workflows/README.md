# Portable agent workflows

This directory is the source of truth for Lei's multi-agent roles and
orchestration rules. It is deliberately independent of Claude Code and Codex.
`scripts/render-agents.py` combines the manifest, role prompts, and shared
contracts into each tool's native agent format during installation.

## Source layout

| Path | Purpose |
|---|---|
| `manifest.json` | Harness-specific machine-readable roles, topology, model policies, message targets, and output limits |
| `runtime-config.*.json` | Schema and initial mutable configuration installed for coordinator confirmation |
| `education-session.schema.json` | Portable state shape for coordinator-registered interactive educator sessions |
| `topology.md` | Human-readable orchestration design and depth rules |
| `roles/` | One provider-neutral prompt per role |
| `workflows/` | Procedures that coordinate several roles |
| `contracts/` | Handoff, routing, state, and output requirements shared by roles |
| `adapters/` | Provider-specific model and sandbox mappings |
| `templates/` | Starting points for human-facing execution artifacts |

## Render and validate

```bash
python3 scripts/render-agents.py --check
python3 scripts/render-agents.py --out /tmp/rendered-agents
```

The renderer writes Claude Markdown under `claude/` and Codex TOML under
`codex/`. Generated files are not checked in: keeping them would create a
second editable copy of every prompt.

## Authoring rules

- Put provider-neutral behavior in Markdown and provider-specific fields in an
  adapter.
- `manifest.json` is this harness's validated schema, not a provider or industry
  standard. Keep detailed responsibility in roles and cross-role sequence in
  workflows rather than duplicating prose in the manifest.
- Keep the root `coordinator` in the manifest, but do not render it as a child
  agent. The main session performs that role through the global prompt.
- Every permitted child edge must fit within `max_depth`.
- Every current child is a leaf and is rendered without agent-spawning ability
  where the provider supports that restriction. `max_depth = 2` remains a
  defensive provider ceiling.
- Mutable learner profiles and execution history never live here. Installed
  state belongs under `$AGENT_HARNESS_HOME/state/`.
- `workflows/education.md` is a standalone coordinator-to-educator path. It
  deliberately bypasses execution preparation, implementation, review, PR
  maintenance, and their artifacts.

## Interactive education adapters

The educator is the only child with `human_interface: registered-session`.
Codex renders stable display nicknames and uses `/agent` for the human focus
switch. Claude Code uses a predictably named agent-team teammate with
`Shift+Down` or a split pane; installation enables its current experimental
agent-team feature. The coordinator registers the session, remains active while
Lei interacts with the educator, and alone closes the session or writes learner
state. Provider lifecycle-stop events wake the coordinator but never determine
that a lesson is complete.
