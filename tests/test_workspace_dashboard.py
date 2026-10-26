from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "agent-skills/agent-workspace/scripts"
sys.path.insert(0, str(HELPERS))
spec = importlib.util.spec_from_file_location("workspace_dashboard", HELPERS / "render_workspace_dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
import dashboard_freshness as freshness


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

    def test_backfill_on_another_machine_uses_its_paths_and_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            _, source_harness = self.fixture(source)
            workspace, harness = self.fixture(destination)
            original = source / "execution-notes/previous-task"
            self.task(original, source_harness, "paused")
            restored = destination / "execution-notes/previous-task"
            shutil.copytree(original, restored)
            readme = (restored / "README.md").read_bytes()
            (harness / "current").mkdir()
            (harness / "current/source").symlink_to(ROOT, target_is_directory=True)
            for name in ("agent-task", "agent-workspace"):
                shutil.copy2(ROOT / f"scripts/{name}.py", harness / "bin" / name)
            env = {**os.environ, "AGENT_HARNESS_HOME": str(harness)}
            command = [sys.executable, str(harness / "bin/agent-task"), "reconcile",
                       str(workspace), str(restored.parent), "--format", "json"]
            for _ in range(2):
                subprocess.run(command, env=env, capture_output=True, check=True)
            result = subprocess.run(
                [sys.executable, str(harness / "bin/agent-workspace"), "list-tasks",
                 "--workspace", str(workspace), "--format", "json"],
                env=env, capture_output=True, text=True, check=True,
            )
            tasks = json.loads(result.stdout)["tasks"]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["path"], str(restored.resolve()))
            self.assertEqual(tasks[0]["id"], "task-one")
            self.assertEqual(tasks[0]["status"], "paused")
            self.assertEqual((restored / "README.md").read_bytes(), readme)
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            page = dashboard.render(snapshot, "<html>map</html>", "refresh")
            self.assertIn(restored.resolve().as_uri(), page)
            self.assertNotIn(original.resolve().as_uri(), page)

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
                 patch.object(dashboard, "collect", return_value={"workspace": str(workspace), "workspace_name": "Example", "tasks": []}), \
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

    def write_report_metadata(self, output, snapshot, age_minutes=0):
        output.write_text("saved dashboard")
        snapshot["max_age_minutes"] = 60.0
        metadata = {
            "schema_version": 1,
            "generated_at": (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat(),
            "input_fingerprint": dashboard.fingerprint(snapshot),
            "output_sha256": freshness.sha256(output), "max_age_minutes": 60.0,
        }
        freshness.metadata_path(output).write_text(json.dumps(metadata))
        return metadata

    def test_freshness_detects_source_and_report_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            self.task(root / "task", harness, "active")
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            output = root / "dashboard.html"
            self.assertEqual(freshness.check_report(output, snapshot, "unused", 60)["freshness"], "missing")
            self.write_report_metadata(output, snapshot)
            check = lambda: freshness.check_report(output, snapshot, dashboard.fingerprint(snapshot), 60)
            self.assertEqual(check()["freshness"], "current")
            # Reobserving identical source data does not force a rebuild.
            snapshot["tasks"][0]["last_seen"] = "2030-01-01T00:00:00+00:00"
            self.assertEqual(check()["freshness"], "current")
            readme = root / "task/README.md"
            readme.write_text(readme.read_text().replace("active", "waiting"))
            self.assertIn("inputs_changed", check()["reasons"])
            output.write_text("changed HTML")
            self.assertIn("report_changed", check()["reasons"])

    def test_age_clock_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                snapshot = dashboard.collect(workspace, None)
            output = root / "dashboard.html"
            self.write_report_metadata(output, snapshot, age_minutes=61)
            check = lambda: freshness.check_report(output, snapshot, dashboard.fingerprint(snapshot), 60)
            self.assertIn("age_limit_exceeded", check()["reasons"])
            self.write_report_metadata(output, snapshot, age_minutes=-10)
            self.assertIn("clock_changed", check()["reasons"])
            freshness.metadata_path(output).write_text("broken JSON")
            self.assertIn("metadata_missing_or_invalid", check()["reasons"])

    def test_refresh_discovers_new_tasks_and_updates_external_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            external = root / "external-task"
            self.task(external, harness, "active")
            readme = external / "README.md"
            readme.write_text(readme.read_text().replace("status: active", "status: paused"))
            new = workspace / "execution-notes/new-task"
            new.mkdir(parents=True)
            (new / "README.md").write_text(readme.read_text().replace("id: task-one", "id: task-two"))
            original = readme.read_bytes()
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                freshness.refresh_catalog(workspace)
                tasks = dashboard.collect(workspace, None)["tasks"]
                self.assertEqual(len(tasks), 2)
                self.assertEqual({task["status"] for task in tasks}, {"paused"})
                self.assertEqual(readme.read_bytes(), original)
                readme.write_text("Broken known task record")
                with self.assertRaisesRegex(ValueError, "discovery refresh failed"):
                    freshness.refresh_catalog(workspace)

    def test_refresh_reuses_current_report_without_archify(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, harness = self.fixture(root)
            self.task(root / "task", harness, "active")
            with patch.dict(os.environ, {"AGENT_HARNESS_HOME": str(harness)}):
                freshness.refresh_catalog(workspace)
                snapshot = dashboard.collect(workspace, None)
            output = root / "dashboard.html"
            self.write_report_metadata(output, snapshot)
            before = output.stat().st_mtime_ns
            for flag, outcome in (("--check", "checked"), ("--refresh", "unchanged")):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/agent-workspace.py"), "dashboard",
                     "--workspace", str(workspace), "--output", str(output), flag,
                     "--archify", str(root / "not-installed"), "--format", "json"],
                    env={**os.environ, "AGENT_HARNESS_HOME": str(harness)},
                    text=True, capture_output=True, check=True,
                )
                self.assertEqual(json.loads(result.stdout)["outcome"], outcome, result.stdout)
                self.assertEqual(json.loads(result.stdout)["freshness"], "current")
                self.assertEqual(output.stat().st_mtime_ns, before)

    def test_git_excludes_only_report_files_and_preserves_existing_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            parent = root / "reports"
            parent.mkdir()
            output = parent / "task [draft] #1.html"
            output.write_text("report")
            freshness.metadata_path(output).write_text("metadata")
            assets = parent / (output.stem + "-assets")
            assets.mkdir()
            (assets / "map.html").write_text("map")
            sibling = parent / "deliverable.html"
            sibling.write_text("keep")
            exclude = root / ".git/info/exclude"
            exclude.write_text("# Existing rules\nkeep-local.txt\n")
            self.assertEqual(freshness.exclude_generated(output)["status"], "ignored")
            first = exclude.read_bytes()
            freshness.exclude_generated(output)
            self.assertEqual(exclude.read_bytes(), first)
            self.assertTrue(first.startswith(b"# Existing rules\nkeep-local.txt\n"))
            for path in (output, freshness.metadata_path(output), assets / "map.html"):
                result = subprocess.run(["git", "-C", str(root), "check-ignore", str(path)], capture_output=True)
                self.assertEqual(result.returncode, 0, path)
            self.assertEqual(subprocess.run(["git", "-C", str(root), "check-ignore", str(sibling)],
                                            capture_output=True).returncode, 1)
            subprocess.run(["git", "-C", str(root), "add", "-f", str(output)], check=True)
            self.assertEqual(freshness.exclude_generated(output)["status"], "already_tracked")


if __name__ == "__main__":
    unittest.main()
