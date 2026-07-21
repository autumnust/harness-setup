from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/render-claude-settings.py"
SPEC = importlib.util.spec_from_file_location("render_claude_settings", MODULE_PATH)
assert SPEC and SPEC.loader
render_claude_settings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_claude_settings)


class RenderClaudeSettingsTests(unittest.TestCase):
    def test_preserves_host_environment_and_removes_retired_agent_teams_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            existing = Path(temp) / "settings.json"
            existing.write_text(
                json.dumps(
                    {
                        "env": {
                            "HOST_ONLY": "preserved",
                            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0",
                        }
                    }
                ),
                encoding="utf-8",
            )
            rendered = render_claude_settings.render(
                REPO_ROOT / "claude/settings.json",
                existing,
                "/usr/local/bin/node",
            )

        self.assertEqual(rendered["env"]["HOST_ONLY"], "preserved")
        self.assertNotIn("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", rendered["env"])


if __name__ == "__main__":
    unittest.main()
