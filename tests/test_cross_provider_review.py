from __future__ import annotations

import argparse
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / "agent-skills/cross-provider-review/scripts/invoke_review.py"
)
SPEC = importlib.util.spec_from_file_location("invoke_review", MODULE_PATH)
assert SPEC and SPEC.loader
invoke_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(invoke_review)


def args(
    caller: str,
    repo: Path,
    *,
    scope: str = "branch",
    base: str | None = "main",
) -> argparse.Namespace:
    return argparse.Namespace(
        caller=caller,
        repo=str(repo),
        scope=scope,
        base=base,
        codex_model="gpt-5.6-sol",
    )


class CrossProviderReviewTests(unittest.TestCase):
    def test_codex_reviewer_invokes_claude_opus_at_max_effort(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            command, provenance = invoke_review.build_command(args("codex", repo))

        self.assertEqual(command[0:2], ["claude", "-p"])
        self.assertIn("independent read-only code-review opinion", command[2])
        self.assertEqual(command[command.index("--model") + 1], "opus")
        self.assertEqual(command[command.index("--effort") + 1], "max")
        self.assertEqual(command[command.index("--permission-mode") + 1], "plan")
        self.assertEqual(
            command[command.index("--tools") + 1],
            "Read,Glob,Grep,Bash(git:*)",
        )
        self.assertIn("--no-session-persistence", command)
        self.assertEqual(
            provenance,
            {
                "caller": "codex",
                "backend": "claude-code",
                "model": "opus",
                "effort": "max",
            },
        )

    def test_claude_reviewer_invokes_codex_plugin_native_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            plugin = root / "plugin"
            companion = plugin / "scripts/codex-companion.mjs"
            companion.parent.mkdir(parents=True)
            companion.write_text("// test runtime\n", encoding="utf-8")
            env = {
                "HARNESS_CODEX_PLUGIN_ROOT": str(plugin),
                "HARNESS_REVIEW_NODE_BIN": "/test/node",
            }
            with patch.dict(os.environ, env, clear=False):
                command, provenance = invoke_review.build_command(
                    args("claude", repo)
                )

        self.assertEqual(command[0], "/test/node")
        self.assertEqual(command[1], str(companion.resolve()))
        self.assertEqual(command[2:4], ["review", "--wait"])
        self.assertEqual(command[command.index("--scope") + 1], "branch")
        self.assertEqual(command[command.index("--base") + 1], "main")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-sol")
        self.assertEqual(
            provenance,
            {
                "caller": "claude",
                "backend": "codex-plugin-native-review",
                "model": "gpt-5.6-sol",
                "effort": "provider-default",
            },
        )

    def test_branch_review_requires_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "requires --base"):
                invoke_review.build_command(
                    args("codex", Path(temp), base=None)
                )


if __name__ == "__main__":
    unittest.main()
