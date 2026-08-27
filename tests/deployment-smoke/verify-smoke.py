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
    claude_adapter = json.loads(
        (repo / "agent-workflows/adapters/claude.json").read_text()
    )
    codex_adapter = json.loads(
        (repo / "agent-workflows/adapters/codex.json").read_text()
    )
    roles = {role["name"]: role for role in manifest["roles"]}
    subagents = {name for name, role in roles.items() if role["kind"] == "subagent"}

    agents_path = home / "AGENTS.md"
    assert agents_path.is_file()
    expected_agents = (
        (repo / "home/AGENTS.md").read_text(encoding="utf-8")
        + "\n"
        + (repo / "instances/example-workstation.md").read_text(encoding="utf-8")
    )
    assert agents_path.read_text(encoding="utf-8") == expected_agents
    assert (
        home / ".agent-harness/instance-profile"
    ).read_text(encoding="utf-8") == "example-workstation\n"
    assert (home / ".claude/CLAUDE.md").resolve() == (home / "AGENTS.md").resolve()
    assert (home / ".codex/AGENTS.md").resolve() == (home / "AGENTS.md").resolve()

    claude_settings = json.loads((home / ".claude/settings.json").read_text())
    assert claude_settings["enabledPlugins"]["smoke-only@example"] is False
    assert claude_settings["env"]["SMOKE_HOST_ONLY"] == "preserved"
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in claude_settings["env"]
    assert (
        claude_settings["model"]
        == claude_adapter["models"]["coordinator"]
        == "sonnet"
    )
    assert claude_settings["effortLevel"] == claude_adapter["effort"]["medium"]

    config = tomllib.loads((home / ".codex/config.toml").read_text())
    assert config["smoke_sentinel"] == "preserved"
    assert (
        config["model"]
        == codex_adapter["models"]["coordinator"]
        == "gpt-5.6-terra"
    )
    assert config["model_reasoning_effort"] == codex_adapter["reasoning_effort"]["medium"]
    assert config["agents"]["max_depth"] == manifest["max_depth"] == 2
    assert config["mcp_servers"]["linear"]["enabled"] is False
    assert config["mcp_servers"]["maas_jira"]["enabled"] is False

    runtime_config = json.loads((home / ".agent-harness/config.json").read_text())
    assert runtime_config["configured"] is True
    assert runtime_config["learner_profile_update_policy"] == "ask"
    assert runtime_config["review_independence"] == "different-foundation"
    assert runtime_config["review_backends"] == [
        {"id": "claude", "foundation": "anthropic"},
        {"id": "codex", "foundation": "openai"},
    ]
    assert runtime_config["pr_maintenance"]["poll_interval_seconds"] == 600
    assert not (home / ".agent-harness/state/education-sessions").exists()

    claude_dir = home / ".claude/agents/agent-harness"
    codex_dir = home / ".codex/agents"
    assert {path.stem for path in claude_dir.glob("*.md")} == subagents
    assert {
        path.stem.removeprefix("agent-harness-")
        for path in codex_dir.glob("agent-harness-*.toml")
    } == subagents

    for name in subagents:
        claude_path = claude_dir / f"{name}.md"
        codex_path = codex_dir / f"agent-harness-{name}.toml"
        verify_frontmatter(claude_path, name)
        codex_agent = tomllib.loads(codex_path.read_text())
        assert codex_agent["name"] == name
        assert codex_agent["nickname_candidates"] == [roles[name]["display_name"]]
        assert codex_agent["model"] == codex_adapter["models"][
            roles[name]["model_policy"]
        ]
        assert codex_agent["model_reasoning_effort"] == codex_adapter[
            "reasoning_effort"
        ][roles[name]["reasoning_policy"]]
        assert codex_agent["description"]
        assert codex_agent["developer_instructions"]
        for contract in roles[name].get("contracts", []):
            heading = (repo / "agent-workflows" / contract).read_text().splitlines()[0]
            assert heading in claude_path.read_text()
            assert heading in codex_agent["developer_instructions"]
        for workflow in roles[name].get("required_workflows", []):
            relative = manifest["workflows"][workflow]
            heading = (repo / "agent-workflows" / relative).read_text().splitlines()[0]
            assert claude_path.read_text().count(heading) == 1
            assert codex_agent["developer_instructions"].count(heading) == 1

    executor = tomllib.loads(
        (codex_dir / "agent-harness-executor.toml").read_text()
    )
    assert executor["model"] == "gpt-5.6-sol"
    assert executor["model_reasoning_effort"] == "high"
    reviewer = tomllib.loads(
        (codex_dir / "agent-harness-reviewer.toml").read_text()
    )
    assert reviewer["model"] == "gpt-5.6-terra"
    assert reviewer["model_reasoning_effort"] == "medium"
    assert "only role permitted" in reviewer["developer_instructions"]
    assert "# PR review workflow" in reviewer["developer_instructions"]
    assert "waits for its opinion" in reviewer["developer_instructions"]
    assert reviewer["developer_instructions"].count("**Finding:**") == 1
    assert "**Suggested action item:**" not in reviewer["developer_instructions"]
    assert "**Disagreement:**" not in reviewer["developer_instructions"]
    maintainer = tomllib.loads(
        (codex_dir / "agent-harness-pr-maintainer.toml").read_text()
    )
    assert maintainer["developer_instructions"].count(
        "# PR maintenance workflow"
    ) == 1
    assert maintainer["developer_instructions"].count(
        "**Registered Executor route:**"
    ) == 1
    assert maintainer["developer_instructions"].count("**Coordinator route:**") == 1

    legacy_claude_dir = home / ".claude/agents/lei-harness"
    assert not (codex_dir / "lei-harness-educator.toml").exists()
    assert not (claude_dir / "educator.md").exists()
    assert list(codex_dir.glob("lei-harness-educator.toml.bak.*"))
    assert list(legacy_claude_dir.glob("educator.md.bak.*"))

    installed_specs = home / ".agent-harness/specs"
    assert file_hashes(repo / "agent-workflows") == file_hashes(installed_specs)
    coordinator_prompt = (
        installed_specs / "roles/coordinator.md"
    ).read_text(encoding="utf-8")
    assert "not a separate agent" in coordinator_prompt
    assert "Teach the human user directly" in coordinator_prompt
    assert "a bounded child for research" in coordinator_prompt
    assert "Do not load a profile outside education" in coordinator_prompt

    expected_skills = file_hashes(repo / "agent-skills")
    for skill_root in (
        home / ".claude/skills",
        home / ".agents/skills",
        home / ".codex/skills",
    ):
        assert file_hashes(skill_root) == expected_skills

    root = home.parent
    codex_route = json.loads((root / "codex-review-route.json").read_text())
    assert codex_route["provenance"] == {
        "caller": "codex",
        "backend": "claude-code",
        "model": "opus",
        "effort": "max",
    }
    codex_command = codex_route["command"]
    assert codex_command[codex_command.index("--model") + 1] == "opus"
    assert codex_command[codex_command.index("--effort") + 1] == "max"
    assert codex_command[codex_command.index("--permission-mode") + 1] == "plan"
    assert codex_command[codex_command.index("--tools") + 1] == "Read,Glob,Grep,Bash"
    assert (
        codex_command[codex_command.index("--allowed-tools") + 1]
        == "Bash(git:*)"
    )
    assert "Smoke review context" in codex_command[2]

    claude_route = json.loads((root / "claude-review-route.json").read_text())
    assert claude_route["provenance"] == {
        "caller": "claude",
        "backend": "codex-plugin-native-review",
        "model": "gpt-5.6-sol",
        "effort": "provider-default",
    }
    claude_command = claude_route["command"]
    assert claude_command[2:4] == ["adversarial-review", "--wait"]
    assert claude_command[claude_command.index("--model") + 1] == "gpt-5.6-sol"
    assert claude_command[-1].startswith("Smoke review context")

    releases = home / ".agent-harness/releases"
    release_ids = [path.name for path in releases.iterdir() if path.is_dir()]
    assert len(release_ids) == 1
    assert (home / ".agent-harness/current").resolve() == (
        releases / release_ids[0]
    ).resolve()
    assert "restored harness release" in (root / "rollback.log").read_text()

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
