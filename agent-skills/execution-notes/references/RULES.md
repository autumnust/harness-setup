# Rule traceability for execution records

This file maps the deterministic checks in
[`check_work_structure.py`](../scripts/check_work_structure.py) to the
authoritative
[`Execution record policy`](../../../home/AGENTS.md#execution-record-policy).
The prose controls when records are needed and what they mean. The checker
covers only file layout and required compact-record headings.

## Compact mode

| Rule | Severity | Policy requirement | Check |
|---|---|---|---|
| `C1` | error | Keep exactly one `RECOVERY.md` in the task folder. | `RECOVERY.md` exists and is readable. |
| `C2` | error | The compact record contains objective, durable decisions, PR and commit state, blockers, latest meaningful validation, and next action. | Each item has a non-empty level-two Markdown section. The checker does not judge whether the prose is correct or concise. |
| `C3` | error | Compact mode has one recovery record and none of the full tracking structure. | No other top-level recovery, progress, dashboard, or tracker Markdown or HTML file exists. Full tracking directories are absent. Ordinary task metadata and product files are ignored. |

The checker cannot determine whether an update happened at a permitted
checkpoint or whether the text copied chat, PR descriptions, GitHub status, or
command output. Those require conversation and source context.

## Full mode

| Rule | Severity | Policy requirement | Check |
|---|---|---|---|
| `S0` | error | When compact tracking expands, move its state into the full structure and stop keeping both formats current. | `RECOVERY.md` is absent. |
| `S1` | error | The full structure has a self-contained `README.md` or `SPEC.md`. | At least one exists at the top level. |
| `S2` | error | Use one `progress.html` status entry point. | `progress.html` exists and no other top-level progress, dashboard, or tracker Markdown or HTML file competes with it. |
| `S3` | error | Keep the top level within the documented roles unless local instructions allow more. | Every visible top-level entry is a documented file or directory, part of the bundled `agent-task` or workspace-task layout identified by README metadata, or appears in `--allow`. |
| `S4` | warning | A `findings/` directory has a catalog. | At least one Markdown file exists in `findings/`. |
| `S5` | warning | Each stage or batch has a runbook and evidence directory. | Each immediate subfolder has `README.md` or a file whose name contains `runbook`, plus `evidence/`. |

The checker does not inspect link quality, browser rendering, phase closure, or
whether work products restate necessary context. Those checks require content
or external state.

When the policy prose changes, update this map and the checker in the same
change.
