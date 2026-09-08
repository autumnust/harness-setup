from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
class CrashRecoveryTests(unittest.TestCase):
    def test_skill_separates_context_recovery_from_runtime_checks(self) -> None:
        skill = (
            REPO_ROOT / "agent-skills" / "crash-recovery" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("task-catalog reconcile", skill)
        self.assertIn("do not contact or recreate TSS sessions", skill)
        self.assertIn("Never change task lifecycle state", skill)
        scripts = REPO_ROOT / "agent-skills" / "crash-recovery" / "scripts"
        self.assertEqual(list(scripts.glob("*.py")), [])


if __name__ == "__main__":
    unittest.main()
