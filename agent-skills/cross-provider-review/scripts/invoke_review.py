#!/usr/bin/env python3
"""Invoke the harness's independent cross-provider review backend."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def version_key(path: Path) -> tuple[int, ...]:
    values = [int(value) for value in re.findall(r"\d+", path.name)]
    return tuple(values) if values else (0,)


def find_codex_plugin_root() -> Path:
    override = os.environ.get("HARNESS_CODEX_PLUGIN_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if (root / "scripts/codex-companion.mjs").is_file():
            return root
        raise FileNotFoundError(f"Codex plugin runtime not found under {root}")

    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    cached = list((claude_dir / "plugins/cache/openai-codex/codex").glob("*"))
    usable = [
        path
        for path in cached
        if (path / "scripts/codex-companion.mjs").is_file()
    ]
    if usable:
        return max(usable, key=version_key)

    marketplace = claude_dir / "plugins/marketplaces/openai-codex/plugins/codex"
    if (marketplace / "scripts/codex-companion.mjs").is_file():
        return marketplace
    raise FileNotFoundError(
        "OpenAI Codex plugin is unavailable; install and enable codex@openai-codex"
    )


def review_target(scope: str, base: str | None) -> str:
    if scope == "branch":
        if not base:
            raise ValueError("branch review requires --base")
        return f"Review the complete diff from {base}...HEAD."
    if scope == "working-tree":
        return "Review all staged, unstaged, and untracked working-tree changes."
    return "Select the appropriate branch or working-tree target from local git state."


def build_command(args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    repo = str(Path(args.repo).resolve())
    if args.caller == "codex":
        prompt = (
            "Provide an independent read-only code-review opinion. Start at the "
            "problem and approach level, then inspect correctness, regressions, "
            "compatibility, and "
            f"missing tests. {review_target(args.scope, args.base)} "
            "Return findings first, ordered by severity, with file references. "
            "State when evidence is uncertain. Do not edit files."
        )
        command = [
            os.environ.get("HARNESS_REVIEW_CLAUDE_BIN", "claude"),
            "-p",
            prompt,
            "--model",
            "opus",
            "--effort",
            "max",
            "--permission-mode",
            "plan",
            "--tools",
            "Read,Glob,Grep,Bash(git:*)",
            "--add-dir",
            repo,
            "--no-session-persistence",
            "--output-format",
            "text",
        ]
        provenance = {
            "caller": "codex",
            "backend": "claude-code",
            "model": "opus",
            "effort": "max",
        }
        return command, provenance

    plugin_root = find_codex_plugin_root()
    command = [
        os.environ.get("HARNESS_REVIEW_NODE_BIN", "node"),
        str(plugin_root / "scripts/codex-companion.mjs"),
        "review",
        "--wait",
        "--scope",
        args.scope,
        "--model",
        args.codex_model,
        "--cwd",
        repo,
    ]
    if args.base:
        command.extend(["--base", args.base])
    provenance = {
        "caller": "claude",
        "backend": "codex-plugin-native-review",
        "model": args.codex_model,
        "effort": "provider-default",
    }
    return command, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caller", choices=("claude", "codex"), required=True)
    parser.add_argument(
        "--scope", choices=("auto", "working-tree", "branch"), default="auto"
    )
    parser.add_argument("--base")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--codex-model", default="gpt-5.6-sol")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        command, provenance = build_command(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps({"command": command, "provenance": provenance}, indent=2))
        return 0

    result = subprocess.run(command, cwd=Path(args.repo).resolve(), text=True)
    if result.returncode:
        print(
            json.dumps({"provenance": provenance, "status": "failed"}),
            file=sys.stderr,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
