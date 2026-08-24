from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "agent-skills" / "agent-task"
HYDRATE = SKILL_ROOT / "scripts" / "hydrate_task.py"
DISCOVER = SKILL_ROOT / "scripts" / "discover_tasks.py"


class AgentTaskTests(unittest.TestCase):
    def run_script(
        self, script: Path, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=check,
            text=True,
            capture_output=True,
        )

    def test_hydrates_into_chosen_destination_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "Daily Life"
            destination.mkdir()
            result = self.run_script(
                HYDRATE,
                "--name", "personal finance",
                "--objective", "Organize accounts and tax records",
                "--destination", str(destination),
            )
            task = destination / "personal finance"
            self.assertEqual(Path(result.stdout.strip()).resolve(), task.resolve())
            self.assertTrue((task / "inbox").is_dir())
            self.assertTrue((task / "outputs").is_dir())
            readme = (task / "README.md").read_text(encoding="utf-8")
            self.assertIn("agent_task: 1", readme)
            self.assertIn("status: active", readme)
            self.assertIn("Organize accounts and tax records", readme)

            repeated = self.run_script(
                HYDRATE,
                "--name", "personal finance",
                "--destination", str(destination),
                check=False,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to overwrite", repeated.stderr)

    def test_discovers_status_and_emits_board_ready_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, status in (("taxes", "blocked"), ("travel", "active")):
                self.run_script(
                    HYDRATE,
                    "--name", name,
                    "--objective", f"Handle {name}",
                    "--destination", str(root),
                )
                readme = root / name / "README.md"
                readme.write_text(
                    readme.read_text(encoding="utf-8").replace(
                        "status: active", f"status: {status}"
                    ),
                    encoding="utf-8",
                )

            result = self.run_script(DISCOVER, str(root), "--format", "json")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(
                [task["title"] for task in payload["tasks"]], ["taxes", "travel"]
            )
            self.assertEqual(
                [task["status"] for task in payload["tasks"]], ["blocked", "active"]
            )
            self.assertEqual(payload["tasks"][0]["objective"], "Handle taxes")
            self.assertEqual(
                payload["tasks"][0]["path"], str((root / "taxes").resolve())
            )
            self.assertEqual(payload["tasks"][0]["runtime_host"], "")
            self.assertEqual(payload["tasks"][0]["tmux_session"], "")
            self.assertEqual(payload["tasks"][0]["tss_target"], "")

    def test_template_is_not_reported_as_a_live_task(self) -> None:
        result = self.run_script(DISCOVER, str(SKILL_ROOT), "--format", "json")
        self.assertEqual(json.loads(result.stdout)["tasks"], [])


if __name__ == "__main__":
    unittest.main()
