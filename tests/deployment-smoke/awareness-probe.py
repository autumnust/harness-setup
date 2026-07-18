#!/usr/bin/env python3
"""Prepare and verify unpredictable markers for online awareness probes."""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Iterable


FIELDS = ("global_marker", "reviewer_marker", "workflow_marker", "skill_marker")
ROLES = {
    "coordinator",
    "exec-env-prepper",
    "executor",
    "reviewer",
    "educator",
    "pr-maintainer",
}


def append_marker(path: Path, label: str, value: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n\nSmoke-test {label}: {value}\n")


def prepare(home: Path, output: Path) -> None:
    markers = {field: f"harness-{field}-{secrets.token_hex(16)}" for field in FIELDS}
    append_marker(home / "AGENTS.md", "global marker", markers["global_marker"])
    append_marker(
        home / ".agent-harness/specs/topology.md",
        "workflow marker",
        markers["workflow_marker"],
    )
    for path in (
        home / ".claude/skills/execution-notes/SKILL.md",
        home / ".agents/skills/execution-notes/SKILL.md",
        home / ".codex/skills/execution-notes/SKILL.md",
    ):
        append_marker(path, "skill marker", markers["skill_marker"])
    append_marker(
        home / ".claude/agents/lei-harness/reviewer.md",
        "reviewer marker",
        markers["reviewer_marker"],
    )

    codex_path = home / ".codex/agents/lei-harness-reviewer.toml"
    text = codex_path.read_text(encoding="utf-8")
    before, separator, after = text.rpartition('\n"""')
    if not separator:
        raise ValueError("cannot find Codex reviewer developer_instructions terminator")
    before += f"\n\nSmoke-test reviewer marker: {markers['reviewer_marker']}"
    codex_path.write_text(before + separator + after, encoding="utf-8")
    output.write_text(json.dumps(markers, indent=2) + "\n", encoding="utf-8")


def candidate_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from candidate_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from candidate_objects(child)
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return
        yield from candidate_objects(parsed)


def verify(provider: str, home: Path, markers_path: Path, response_path: Path) -> None:
    markers = json.loads(markers_path.read_text())
    response = json.loads(response_path.read_text())
    candidate = next(
        (
            item
            for item in candidate_objects(response)
            if all(field in item for field in FIELDS)
        ),
        None,
    )
    if candidate is None:
        raise ValueError("no structured awareness result found")
    assert candidate["provider"] == provider
    for field, expected in markers.items():
        assert candidate[field] == expected, f"incorrect {field}"
    assert set(candidate["available_roles"]) == ROLES
    assert candidate["max_depth"] == 2
    assert candidate["educator_is_leaf"] is True
    expected_state = home / ".agent-harness/state/learner-profiles"
    reported_state = candidate["state_path"]
    accepted_paths = {
        str(expected_state),
        "~/.agent-harness/state/learner-profiles",
        "$AGENT_HARNESS_HOME/state/learner-profiles",
    }
    assert reported_state in accepted_paths, f"incorrect state_path: {reported_state}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--home", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--provider", choices=("claude", "codex"), required=True)
    verify_parser.add_argument("--home", type=Path, required=True)
    verify_parser.add_argument("--markers", type=Path, required=True)
    verify_parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.home, args.output)
        else:
            verify(args.provider, args.home, args.markers, args.response)
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: awareness {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
