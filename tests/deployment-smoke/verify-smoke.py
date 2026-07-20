#!/usr/bin/env python3
"""Deterministic assertions for the deployment smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise SystemExit("Python 3.11 or newer is required for deployment smoke tests") from exc


def file_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def verify_frontmatter(path: Path, expected_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3, f"missing front matter: {path}"
    frontmatter = parts[1]
    assert f"\nname: {expected_name}\n" in f"\n{frontmatter}\n"
    assert "\ndescription: " in f"\n{frontmatter}"
    assert "\nmodel: " in f"\n{frontmatter}"


def verify_install(repo: Path, home: Path, update_log: Path) -> None:
    manifest = json.loads((repo / "agent-workflows/manifest.json").read_text())
    roles = {role["name"]: role for role in manifest["roles"]}
    subagents = {name for name, role in roles.items() if role["kind"] == "subagent"}

    assert (home / "AGENTS.md").is_file()
    assert (home / ".claude/CLAUDE.md").resolve() == (home / "AGENTS.md").resolve()
    assert (home / ".codex/AGENTS.md").resolve() == (home / "AGENTS.md").resolve()

    claude_settings = json.loads((home / ".claude/settings.json").read_text())
    assert claude_settings["enabledPlugins"]["smoke-only@example"] is False

    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert config["smoke_sentinel"] == "preserved"
    assert config["agents"]["max_depth"] == manifest["max_depth"] == 2

    runtime_config = json.loads((home / ".agent-harness/config.json").read_text())
    assert runtime_config["configured"] is True
    assert runtime_config["review_independence"] == "different-foundation"
    assert runtime_config["review_backends"] == [
        {"id": "claude", "foundation": "anthropic"},
        {"id": "codex", "foundation": "openai"},
    ]
    assert runtime_config["pr_maintenance"]["poll_interval_seconds"] == 600

    claude_dir = home / ".claude/agents/lei-harness"
    codex_dir = home / ".codex/agents"
    assert {path.stem for path in claude_dir.glob("*.md")} == subagents
    assert {
        path.stem.removeprefix("lei-harness-") for path in codex_dir.glob("lei-harness-*.toml")
    } == subagents

    for name in subagents:
        claude_path = claude_dir / f"{name}.md"
        codex_path = codex_dir / f"lei-harness-{name}.toml"
        verify_frontmatter(claude_path, name)
        codex_agent = tomllib.loads(codex_path.read_text())
        assert codex_agent["name"] == name
        assert codex_agent["description"]
        assert codex_agent["developer_instructions"]
        for contract in roles[name].get("contracts", []):
            heading = (repo / "agent-workflows" / contract).read_text().splitlines()[0]
            assert heading in claude_path.read_text()
            assert heading in codex_agent["developer_instructions"]

    installed_specs = home / ".agent-harness/specs"
    assert file_hashes(repo / "agent-workflows") == file_hashes(installed_specs)

    skill_names = {
        path.parent.name for path in (repo / "agent-skills").glob("*/SKILL.md")
    }
    for skill_root in (
        home / ".claude/skills",
        home / ".agents/skills",
        home / ".codex/skills",
    ):
        assert {path.parent.name for path in skill_root.glob("*/SKILL.md")} == skill_names

    learner = home / ".agent-harness/state/learner-profiles/smoke.md"
    assert "must survive update" in learner.read_text()
    assert "Harness sync complete: 0 updated" in update_log.read_text()


def verify_doctors(
    claude_status: int, claude_log: Path, codex_status: int, codex_report: Path
) -> None:
    assert claude_status == 0, f"claude doctor exited {claude_status}"
    claude_text = claude_log.read_text(errors="replace").lower()
    assert "invalid settings" not in claude_text
    assert "settings validation error" not in claude_text

    assert codex_status in {0, 1}, f"codex doctor exited unexpectedly: {codex_status}"
    report = json.loads(codex_report.read_text())
    checks = report["checks"]
    assert checks["config.load"]["status"] == "ok"
    assert checks["config.load"]["details"]["config.toml parse"] == "ok"
    failed = {key for key, value in checks.items() if value["status"] == "fail"}
    allowed = {"auth.credentials", "network.provider_reachability"}
    assert failed <= allowed, f"unexpected Codex doctor failures: {sorted(failed - allowed)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install")
    install.add_argument("--repo", type=Path, required=True)
    install.add_argument("--home", type=Path, required=True)
    install.add_argument("--update-log", type=Path, required=True)

    doctors = subparsers.add_parser("doctors")
    doctors.add_argument("--claude-status", type=int, required=True)
    doctors.add_argument("--claude-log", type=Path, required=True)
    doctors.add_argument("--codex-status", type=int, required=True)
    doctors.add_argument("--codex-report", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "install":
            verify_install(args.repo, args.home, args.update_log)
        else:
            verify_doctors(
                args.claude_status,
                args.claude_log,
                args.codex_status,
                args.codex_report,
            )
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {args.command} assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
