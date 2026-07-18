# Portable agent workflows

This directory is the source of truth for Lei's multi-agent roles and
orchestration rules. It is deliberately independent of Claude Code and Codex.
`scripts/render-agents.py` combines the manifest, role prompts, and shared
contracts into each tool's native agent format during installation.

## Source layout

| Path | Purpose |
|---|---|
| `manifest.json` | Machine-readable roles, topology, model policies, and output limits |
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
- Keep the root `coordinator` in the manifest, but do not render it as a child
  agent. The main session performs that role through the global prompt.
- Every permitted child edge must fit within `max_depth`.
- A role with no permitted children is rendered without the ability to spawn
  another agent where the provider supports that restriction.
- Mutable learner profiles and execution history never live here. Installed
  state belongs under `$AGENT_HARNESS_HOME/state/`.
