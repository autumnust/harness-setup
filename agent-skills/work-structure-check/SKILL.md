---
name: work-structure-check
description: Validate a long-running execution folder against the "Long-Running Work Structure" contract in ~/AGENTS.md — required README/SPEC, a single progress.html entry point, a clean top level, a findings catalog, and per-stage runbook + evidence — then fix the violations it reports. Use when setting up, reorganizing, auditing, or finishing a multi-step / multi-session execution folder, or before committing or opening a PR that includes one.
---

# Work Structure Check

A deterministic, structure-only linter for a long-running execution folder, plus
the procedure to act on its findings. The rules come from the **Long-Running
Work Structure** section of `~/AGENTS.md`; `RULES.md` in this directory maps each
check back to the exact sentence it is deduced from.

## When to use

Use this only for **large, multi-step / multi-session work** that keeps running
artifacts in an execution folder. Good moments to run it:

- right after creating the execution folder — validate the skeleton early;
- before committing or opening a PR that includes the folder;
- when reorganizing the folder or closing out a phase.

Skip it for small or one-off changes — the contract does not apply there, and
the linter would flag a folder that was never meant to follow it.

## How to run

The linter sits next to this file, in this skill's own directory — for Claude
Code that's `~/.claude/skills/work-structure-check/`, for Codex CLI it's
`~/.codex/skills/work-structure-check/`:

```
python3 <this-skill-directory>/check_work_structure.py <execution-folder>
```

Exit code `0` = conforms, `1` = at least one error (or, with `--strict`, any
warning). Useful flags:

- `--json` — machine-readable findings
- `--strict` — treat warnings as errors for the exit code
- `--allow NAME` — permit an extra top-level entry name (repeatable)

## How to read and fix the findings

Each finding carries a rule id. Fix the folder, then re-run until it is clean —
do **not** weaken a rule to make it pass.

| Rule | What it means | How to fix |
|---|---|---|
| **S1** (error) | no `README.md` / `SPEC.md` at the top level | add a self-contained spec: goal, success criteria, folder layout, how to add work, how to resume |
| **S2** (error) | missing, wrong-named, or competing progress dashboard | keep exactly one `progress.html`; fold any other tracker into it |
| **S3** (error) | a stray top-level file/dir | move it into `findings/`, `evidence/`, or a stage folder — or pass `--allow NAME` if it legitimately belongs |
| **S4** (warn) | `findings/` has no catalog | add a `.md` catalog listing issues with status (keep closed items visible, marked closed) |
| **S5** (warn) | a stage folder lacks a runbook or `evidence/` | give each `stages/`/`batches/` subfolder its own `README.md`/runbook and an `evidence/` directory |

## If a rule itself seems wrong

The prose in `~/AGENTS.md` is the source of truth, not the script. If a check
disagrees with the contract, change the prose and the check together — see
`RULES.md`, which records how each check was deduced and must be kept in sync.
