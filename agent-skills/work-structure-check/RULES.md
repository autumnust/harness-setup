# Rule traceability — `work-structure-check`

Provenance map for the skill's linter: how each deterministic check is deduced
from the natural-language contract. Companion to `SKILL.md` (how to run and fix)
and `check_work_structure.py` (the engine).

A deterministic, stdlib-only linter that validates an execution folder against the
**Long-Running Work Structure** contract.

- Run it: see the module docstring in
  [`check_work_structure.py`](./check_work_structure.py) for usage and flags.
- Source of the rules:
  [`home/AGENTS.md` § Long-Running Work Structure](../../home/AGENTS.md#long-running-work-structure)
  ([same section on GitHub](https://github.com/autumnust/harness-setup/blob/e33602c/home/AGENTS.md#long-running-work-structure)),
  which is deployed to `~/AGENTS.md` on every machine.

### Why this file exists: the rules are *deduced* from prose

The section in `AGENTS.md` is a natural-language description of how a long-running
execution folder should be laid out. The checks `S1`–`S5` in the script are a
**deterministic interpretation** of that prose — they are *not* the authoritative
rule. The prose is the source of truth; the script is a best-effort,
mechanically-checkable subset of it.

Deducing a check from a sentence involves judgment (e.g. the prose lists a
`README.md` as a contract role but never says the word "required" — the script
*treats* it as required). This file records that judgment so that:

1. **When the prose changes**, you can see which checks to revisit.
2. **Anyone can audit** whether a check faithfully represents the sentence it came
   from, instead of reverse-engineering it from code.

### Traceability: each check → the sentence it encodes

| Rule | Severity | Sentence(s) it encodes (from the section) | Deterministic check | Interpretation / judgment applied |
|---|---|---|---|---|
| **S1** | error | Contract table row: *"`README.md` / `SPEC.md` — Self-contained 'what and how': goal, success criteria, folder layout, how to add work, and how to resume."* | top level has `README.md` or `SPEC.md` | The table lists it as a role but doesn't say "required." Deduced as **required**: a folder with no self-contained spec has no entry point, so its absence is an error. Content of the spec is not checked — only presence. |
| **S2** | error | *"Use one progress entry point. Prefer one visual dashboard as the status entry point; avoid multiple competing trackers…"* + contract row *"`progress.html` — Human/agent dashboard for 'where we are'…"* | exactly one progress dashboard; flags none, a wrong-named one, or competing trackers | "Progress entry point" deduced as **required and named `progress.html`**. "Competing tracker" operationalized as any *other* top-level file matching `progress` / `dashboard` / `tracker` (`.html`/`.md`). |
| **S3** | error | *"Use an execution-folder contract, not ad hoc files… keep the top-level execution folder small"* + *"Keep the top level clean. Do not create one-off top-level runbooks, trackers, or evidence folders."* + *"Pick an execution folder first… don't scatter files."* | every top-level entry must be a contract role (`README.md`/`SPEC.md`/`progress.html`, or `findings/`/`evidence/`/`logs/`/`stages/`/`batches/`); anything else is flagged | "Ad hoc / one-off" deduced as **any top-level entry outside the role set**. The `--allow NAME` flag is the partial honoring of *"Unless local `AGENTS.md` or `README.md` says otherwise"* — a full per-folder override is not yet implemented. |
| **S4** | warning | Contract row: *"`findings/` — … Keep a catalog with ticket links, source scenario, status, and resolution."* | if `findings/` exists, it must contain at least one `.md` file | Only the **presence of a catalog** is checkable deterministically; its completeness (ticket links, status columns, closed-but-visible items) is content and is **not** verified — hence a warning, not an error. |
| **S5** | warning | Contract row: *"`stages/` or `batches/` — … Each stage has its own `README.md` or runbook and `evidence/`…"* | each immediate subfolder of `stages/`/`batches/` has a `README.md` or `*runbook*` file **and** an `evidence/` directory | Direct, structural mapping. Whether each stage actually *"updates the top-level `progress.html` and findings/"* is a cross-file content claim and is **not** verified. |

### Sentences in the section deliberately **not** encoded

These are real rules in the same section, left out because they are about file
*content* or require judgment — outside a structure-only, deterministic linter.
Listed so the omission is visible rather than silent:

| Sentence | Why not encoded |
|---|---|
| *"Link all references… clickable hyperlink — never bare text."* | Content of generated files; needs parsing prose, not layout. |
| *"Keep generated dashboards and specs self-contained…"* | Requires judging whether prose is understandable without chat history. |
| *"Close phases explicitly… mark it closed…"* | Requires reading status content inside the files. |
| *"Keep work products self-contained… PR descriptions, commit messages… never reference the execution artifacts…"* | Operates on diffs / PR / commit text, not the execution folder layout. |

These could be picked up later by a separate content/PR checker (lint for bare
links; an LLM judge for the self-containment and phase-closure rules).

### Keeping the script and the prose in sync

The prose is authoritative. If you edit
[§ Long-Running Work Structure](../../home/AGENTS.md#long-running-work-structure),
re-read this table and update any affected check (or this mapping) in the same
change, so the two never silently drift apart.
