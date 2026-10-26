from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "agent-skills/agent-workspace/scripts"
sys.path.insert(0, str(HELPERS))
spec = importlib.util.spec_from_file_location("workspace_dashboard", HELPERS / "render_workspace_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class WorkspaceDashboardTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "workspace.yaml").write_text(
            "schema_version: 2\nworkspace:\n  id: 'workspace-one'\n  name: 'Example workspace'\nrepositories:\n"
        )
        harness = root / "harness"
        (harness / "bin").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/task-catalog.py", harness / "bin/task-catalog")
        return workspace, harness

    def task(self, path: Path, harness: Path, status: str, workspace_id: str = "workspace-one", task_id: str = "task-one") -> None:
        path.mkdir(parents=True)
        (path / "README.md").write_text(
            f"---\nworkspace_task: 1\nid: {task_id}\nworkspace_id: {workspace_id}\n"
            f"workspace: Example workspace\ntitle: {path.name}\nstatus: {status}\n---\n"
            "# Task\n\n## Current objective\nBuild the requested change.\n\n"
            "## Current state\nReady for work.\n\n## Immediate next task\nRun the checks.\n"
        )
        subprocess.run([sys.executable, str(harness / "bin/task-catalog"), "register", "--path", str(path)],
                       env={**os.environ, "AGENT_HARNESS_HOME": str(harness)}, capture_output=True, check=True)

    def test_membership_filtering_external_locations_and_read_only_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            outside = root / "execution-notes/active"
            self.task(outside, harness, "active")
            self.task(root / "other-copy/active", harness, "active")
            self.task(workspace / "tasks/paused", harness, "paused", task_id="paused")
            self.task(workspace / "tasks/foreign", harness, "active", "different-workspace", "foreign")
            catalog = harness / "state/task-catalog/catalog.sqlite3"
            before = catalog.read_bytes()
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, {"active"})
            self.assertEqual(len(snapshot["tasks"]), 2)
            self.assertEqual({task["id"] for task in snapshot["tasks"]}, {"task-one"})
            self.assertEqual(snapshot["tasks"][0]["objective"], "Build the requested change.")
            self.assertEqual(catalog.read_bytes(), before)
            tree = dashboard.tree_source(snapshot)
            self.assertEqual(len(tree["nodes"]), 5)
            self.assertEqual(len({n["id"] for n in tree["nodes"]}), 5)

    def test_missing_folder_is_checked_at_render_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            task = root / "gone"
            self.task(task, harness, "active")
            shutil.rmtree(task)
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            self.assertFalse(snapshot["tasks"][0]["present"])
            self.assertEqual(snapshot["tasks"][0]["links"], [])
            self.assertIn("folder missing", dashboard.tree_source(snapshot)["nodes"][-1]["sublabel"])

    def test_empty_workspace_has_valid_root_and_empty_message(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            self.assertEqual(len(dashboard.tree_source(snapshot)["nodes"]), 1)
            page = dashboard.render(snapshot, "<html>diagram</html>", "refresh")
            self.assertIn('class="empty" >', page)
            self.assertIn("No tasks match", page)

    def test_untrusted_task_text_stays_text_and_links_are_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            self.task(root / "task", harness, "active")
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            task = snapshot["tasks"][0]
            (root / "task/progress.html").write_text("Progress")
            (root / "task/report file.html").write_text("Report")
            task["task_name"] = '<img src=x onerror="alert(1)"> @@title@@'
            task["objective"] = '</script><script>alert(1)</script> [report](report%20file.html) [bad](javascript:alert)'
            task["next_task"] = '[Progress](progress.html) [Docs](https://example.com/doc?a=1&b=2)'
            page = dashboard.render(snapshot, "<html>diagram</html>", "refresh")
            self.assertNotIn('<img src=x', page)
            self.assertNotIn('<script>alert(1)</script>', page)
            self.assertNotIn('href="javascript:', page)
            self.assertIn('@@title@@', page)
            self.assertIn((root / "task/progress.html").resolve().as_uri(), page)
            self.assertIn((root / "task/report file.html").resolve().as_uri(), page)
            self.assertIn('https://example.com/doc?a=1&amp;b=2', page)
            self.assertIn('srcdoc="&lt;html&gt;', page)

    def test_missing_document_links_are_marked_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            rendered = dashboard.linked_text("Read [report](missing.docx).", folder)
            self.assertIn("report (file unavailable)", rendered)
            self.assertNotIn("href=", rendered)
            self.assertIn("missing.docx", rendered)

    def test_failed_archify_keeps_previous_dashboard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            output = root / "dashboard.html"
            output.write_text("previous dashboard")
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}), \
                 patch.object(dashboard, "find_archify", return_value=root / "archify.mjs"), \
                 patch.object(dashboard.shutil, "which", return_value="node"), \
                 patch.object(dashboard, "collect", return_value={"workspace_name": "Example", "tasks": []}), \
                 patch.object(dashboard.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "failed", "")):
                with self.assertRaisesRegex(ValueError, "previous dashboard kept"):
                    dashboard.generate(workspace, output, None, None)
            self.assertEqual(output.read_text(), "previous dashboard")
            self.assertEqual(len(list(root.glob("dashboard-assets/render-*/render.log"))), 1)

    def test_cli_reports_missing_archify_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, _ = self.fixture(root)
            output = root / "dashboard.html"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/agent-workspace.py"),
                                     "dashboard", "--workspace", str(workspace), "--output", str(output),
                                     "--archify", str(root / "missing"), "--format", "json"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Archify is unavailable", json.loads(result.stdout)["error"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
