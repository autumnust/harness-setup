# Agent operating instructions

1. Before starting, read `README.md`, `tasks.md`, and relevant material in `context/`.
2. Treat `inbox/` as raw evidence, not established truth.
3. Clearly distinguish facts, assumptions, interpretations, and unknowns.
4. Ask only when an unresolved choice would materially change the result.
5. Prefer small, reviewable changes; avoid unnecessary complexity.
6. Update `decisions.md` when making an important decision.
7. Update `tasks.md` as work progresses.
8. Put intermediate artifacts in `work/` and final deliverables in `outputs/`.
9. Preserve existing user content; never silently discard conflicting information.
10. Keep the workspace concise by consolidating outdated or duplicate context while preserving important history.
11. For an explicit natural-language task-state request, map start or resume to `active`, pause to `paused`, waiting to `waiting`, a blocker to `blocked`, finish to `done`, and cancel or abandon to `cancelled`, then run `agent-task set-state --task-dir "<this-task-folder>" --status <status> --summary "<current state or outcome>" [--next-step "<next action or resume trigger>"] --format json`; never infer state from a conversation or runtime ending.
