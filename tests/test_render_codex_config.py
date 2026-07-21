from __future__ import annotations

import importlib.util
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/render-codex-config.py"
SPEC = importlib.util.spec_from_file_location("render_codex_config", MODULE_PATH)
assert SPEC and SPEC.loader
render_codex_config = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_codex_config)


class RenderCodexConfigTests(unittest.TestCase):
    def test_sets_coordinator_policy_and_preserves_unrelated_config(self) -> None:
        source = """smoke_sentinel = \"preserved\"
model = \"old-model\"

[agents]
max_depth = 1

[mcp_servers.example]
command = \"example\"
"""
        rendered = render_codex_config.render(
            source,
            depth=2,
            model="fast-model",
            reasoning_effort="medium",
        )
        parsed = tomllib.loads(rendered)

        self.assertEqual(parsed["smoke_sentinel"], "preserved")
        self.assertEqual(parsed["model"], "fast-model")
        self.assertEqual(parsed["model_reasoning_effort"], "medium")
        self.assertEqual(parsed["agents"]["max_depth"], 2)
        self.assertEqual(parsed["mcp_servers"]["example"]["command"], "example")

    def test_inserts_agents_table_before_existing_child_table(self) -> None:
        rendered = render_codex_config.render(
            "[agents.executor]\nmax_threads = 1\n",
            depth=2,
            model="fast-model",
            reasoning_effort="medium",
        )
        parsed = tomllib.loads(rendered)

        self.assertEqual(parsed["agents"]["max_depth"], 2)
        self.assertEqual(parsed["agents"]["executor"]["max_threads"], 1)


if __name__ == "__main__":
    unittest.main()
