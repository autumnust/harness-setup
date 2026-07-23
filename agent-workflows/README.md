# Portable agent workflows

This directory is the source of truth for the harness's multi-agent roles and
orchestration rules. It is deliberately independent of Claude Code and Codex.
`scripts/render-agents.py` combines the manifest, role prompts, and shared
contracts into each tool's native agent format during installation.

## Source layout

| Path | Purpose |
|---|---|
| `manifest.json` | Harness-specific machine-readable roles, topology, model policies, message targets, and output limits |
| `runtime-config.*.json` | Schema and initial mutable configuration installed for coordinator confirmation |
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
- Declare a role's `required_workflows` in the manifest when generated native
  agent instructions must include a workflow. Keep ordered multi-role process
  and result-category definitions in that workflow rather than repeating them
  in the role prompt.
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
- `workflows/education.md` defines an interactive coordinator mode. It loads
  learner state only on entry, teaches in the root session, and considers a
  profile update only on exit.

## Interactive education

Education is not a rendered child. The coordinator enters the mode only after
an explicit request or accepted suggestion, and continues using its provider
adapter's fast model policy. It may delegate bounded evidence collection,
experiments, or teaching artifacts to operational children while keeping the
interactive lesson in the root session. Small lessons create no execution
artifacts; large experiments still follow execution-preparation rules.
