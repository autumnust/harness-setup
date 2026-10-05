from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = (
    REPO_ROOT
    / "agent-skills"
    / "execution-notes"
    / "scripts"
    / "check_work_structure.py"
)
TEMPLATE_PATH = (
    REPO_ROOT
    / "agent-skills"
    / "execution-notes"
    / "assets"
    / "RECOVERY.md"
)
SPEC = importlib.util.spec_from_file_location("check_work_structure", CHECKER_PATH)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class ExecutionRecordTests(unittest.TestCase):
    def test_compact_template_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "RECOVERY.md").write_text(TEMPLATE_PATH.read_text())
            self.assertEqual(checker.check_structure(folder, set(), "compact"), [])

    def test_compact_requires_every_recovery_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            content = TEMPLATE_PATH.read_text().replace("## Blockers", "## Delays")
            (folder / "RECOVERY.md").write_text(content)
            findings = checker.check_structure(folder, set(), "compact")
            self.assertIn("C2", {finding.rule for finding in findings})
            self.assertTrue(any("Blockers" in finding.message for finding in findings))

    def test_compact_rejects_full_tracking_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "RECOVERY.md").write_text(TEMPLATE_PATH.read_text())
            (folder / "progress.html").write_text("<p>status</p>")
            (folder / "evidence").mkdir()
            findings = checker.check_structure(folder, set(), "compact")
            self.assertEqual([finding.rule for finding in findings], ["C3", "C3"])

    def test_full_structure_passes_without_compact_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "README.md").write_text("# Task\n")
            (folder / "progress.html").write_text("<p>status</p>")
            self.assertEqual(checker.check_structure(folder, set(), "full"), [])

    def test_full_structure_accepts_bundled_task_context_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "README.md").write_text("---\nagent_task: 1\n---\n# Task\n")
            (folder / "progress.html").write_text("<p>status</p>")
            (folder / "AGENTS.md").write_text("# Instructions\n")
            (folder / "tasks.md").write_text("# Tasks\n")
            (folder / "context").mkdir()
            self.assertEqual(checker.check_structure(folder, set(), "full"), [])

    def test_full_structure_rejects_compact_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "README.md").write_text("# Task\n")
            (folder / "progress.html").write_text("<p>status</p>")
            (folder / "RECOVERY.md").write_text(TEMPLATE_PATH.read_text())
            findings = checker.check_structure(folder, set(), "full")
            self.assertIn("S0", {finding.rule for finding in findings})


if __name__ == "__main__":
    unittest.main()
