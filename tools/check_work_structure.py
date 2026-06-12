#!/usr/bin/env python3
"""Validate an execution folder against the Long-Running Work Structure contract.

Source of truth: ~/AGENTS.md (home/AGENTS.md in the harness-setup repo),
section "Long-Running Work Structure". The S1-S5 rules below are a deterministic
*interpretation* of that prose, not the rule itself. tools/README.md records,
rule by rule, which sentence each check was deduced from and what judgment was
applied — read it before changing a check or the prose.

This is a STRUCTURE-only linter. It inspects the folder layout — which files and
directories exist and where — and nothing about file *contents*. No model calls,
no diff/PR parsing, no prose grading. Pure, deterministic, fast.

The contract (top-level roles):

    README.md / SPEC.md   self-contained "what and how"            (required)
    progress.html         single status dashboard / entry point    (required)
    findings/             catalog of issues found while executing   (optional)
    evidence/ | logs/     raw logs, traces, dry-run JSON, output    (optional)
    stages/ | batches/    per-stage runbooks + evidence (large)     (optional)

Rules enforced:

    S1  README.md or SPEC.md present at the top level.            (error)
    S2  Exactly one progress dashboard; none others compete.      (error)
    S3  Top level is clean: no entry outside the contract roles.  (error)
    S4  If findings/ exists, it carries a catalog (a .md file).   (warning)
    S5  Each stages/|batches/ subfolder has its own README or     (warning)
        runbook AND an evidence/ directory.

Usage:
    check_work_structure.py <execution-folder> [--json] [--strict] [--allow NAME ...]

    --json          emit findings as JSON instead of human-readable text
    --strict        treat warnings as errors for the exit code
    --allow NAME    permit an extra top-level entry name (repeatable),
                    e.g. --allow assets --allow .gitignore

Exit code: 0 if the folder conforms (no errors; no warnings under --strict),
1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CONTRACT_REF = "~/AGENTS.md § Long-Running Work Structure"

# Top-level entries the contract sanctions.
ALLOWED_FILES = {"README.md", "SPEC.md", "progress.html"}
ALLOWED_DIRS = {"findings", "evidence", "logs", "stages", "batches"}
STAGE_DIRS = {"stages", "batches"}


@dataclass
class Finding:
    rule: str
    severity: str  # "error" | "warning"
    path: str
    message: str
    contract_ref: str = CONTRACT_REF


def _is_progress_dashboard(name: str) -> bool:
    """A top-level file that reads as a status dashboard / progress tracker."""
    low = name.lower()
    if not low.endswith((".html", ".md")):
        return False
    return "progress" in low or "dashboard" in low or "tracker" in low


def _visible_entries(folder: Path) -> list[Path]:
    """Top-level entries, ignoring dotfiles (.git, .gitkeep, etc.)."""
    return sorted(
        (p for p in folder.iterdir() if not p.name.startswith(".")),
        key=lambda p: p.name,
    )


def check_structure(folder: Path, allow: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    entries = _visible_entries(folder)
    names = {p.name for p in entries}

    # S1 — a self-contained spec must exist.
    if not (names & {"README.md", "SPEC.md"}):
        findings.append(
            Finding(
                "S1",
                "error",
                str(folder),
                "missing README.md or SPEC.md (the self-contained 'what and how').",
            )
        )

    # S2 — exactly one progress entry point; flag absence and competition.
    dashboards = [p.name for p in entries if p.is_file() and _is_progress_dashboard(p.name)]
    if not dashboards:
        findings.append(
            Finding(
                "S2",
                "error",
                str(folder),
                "no progress entry point — expected a single progress.html dashboard.",
            )
        )
    elif "progress.html" not in dashboards:
        findings.append(
            Finding(
                "S2",
                "error",
                str(folder),
                f"progress dashboard is named {dashboards[0]!r}; the contract entry "
                "point is progress.html.",
            )
        )
    elif len(dashboards) > 1:
        others = [d for d in dashboards if d != "progress.html"]
        findings.append(
            Finding(
                "S2",
                "error",
                str(folder),
                f"competing progress trackers besides progress.html: {others} — "
                "keep one entry point.",
            )
        )

    # S3 — top level holds only contract roles (plus user allowlist).
    for p in entries:
        if p.name in allow:
            continue
        if p.is_file() and p.name in ALLOWED_FILES:
            continue
        if p.is_dir() and p.name in ALLOWED_DIRS:
            continue
        kind = "directory" if p.is_dir() else "file"
        findings.append(
            Finding(
                "S3",
                "error",
                str(p),
                f"stray top-level {kind} {p.name!r} — not a contract role; move it "
                "into findings/, evidence/, or a stage folder (or pass --allow).",
            )
        )

    # S4 — findings/ should carry a catalog.
    findings_dir = folder / "findings"
    if findings_dir.is_dir():
        has_catalog = any(c.suffix == ".md" for c in findings_dir.iterdir() if c.is_file())
        if not has_catalog:
            findings.append(
                Finding(
                    "S4",
                    "warning",
                    str(findings_dir),
                    "findings/ has no catalog (a .md listing issues with status).",
                )
            )

    # S5 — each stage/batch subfolder is self-describing with its own evidence.
    for stage_root_name in STAGE_DIRS:
        stage_root = folder / stage_root_name
        if not stage_root.is_dir():
            continue
        for stage in sorted(p for p in stage_root.iterdir() if p.is_dir()):
            stage_names = {c.name.lower() for c in stage.iterdir()}
            has_doc = "readme.md" in stage_names or any("runbook" in n for n in stage_names)
            if not has_doc:
                findings.append(
                    Finding(
                        "S5",
                        "warning",
                        str(stage),
                        "stage folder has no README.md or runbook.",
                    )
                )
            if not (stage / "evidence").is_dir():
                findings.append(
                    Finding(
                        "S5",
                        "warning",
                        str(stage),
                        "stage folder has no evidence/ directory.",
                    )
                )

    return findings


def render_text(folder: Path, findings: list[Finding]) -> str:
    if not findings:
        return f"OK  {folder}  — conforms to the Long-Running Work Structure contract."
    lines = [f"FAIL  {folder}", ""]
    for f in sorted(findings, key=lambda f: (f.severity != "error", f.rule, f.path)):
        tag = "ERROR " if f.severity == "error" else "warn  "
        lines.append(f"  [{tag}{f.rule}] {f.path}")
        lines.append(f"           {f.message}")
    n_err = sum(1 for f in findings if f.severity == "error")
    n_warn = len(findings) - n_err
    lines.append("")
    lines.append(f"  {n_err} error(s), {n_warn} warning(s) — per {CONTRACT_REF}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an execution folder against the Long-Running Work "
        "Structure contract (~/AGENTS.md).",
    )
    parser.add_argument("folder", type=Path, help="path to the execution folder")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument(
        "--strict", action="store_true", help="treat warnings as errors for exit code"
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="NAME",
        help="permit an extra top-level entry name (repeatable)",
    )
    args = parser.parse_args(argv)

    folder: Path = args.folder
    if not folder.exists():
        print(f"error: no such folder: {folder}", file=sys.stderr)
        return 2
    if not folder.is_dir():
        print(f"error: not a directory: {folder}", file=sys.stderr)
        return 2

    findings = check_structure(folder, set(args.allow))

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(render_text(folder, findings))

    has_error = any(f.severity == "error" for f in findings)
    has_warning = any(f.severity == "warning" for f in findings)
    return 1 if has_error or (args.strict and has_warning) else 0


if __name__ == "__main__":
    raise SystemExit(main())
