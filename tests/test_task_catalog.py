from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "scripts" / "task-catalog.py"


def load_catalog_module():
    spec = importlib.util.spec_from_file_location("task_catalog", CATALOG)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load task-catalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskCatalogTests(unittest.TestCase):
    def run_catalog(
        self,
        database: Path,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(CATALOG), "--db", str(database), *arguments],
            check=False,
            text=True,
            capture_output=True,
        )
        if check and result.returncode != 0:
            self.fail(f"task-catalog failed: {result.stderr}")
        return result

    def write_workspace(self, path: Path, workspace_id: str = "workspace-1") -> None:
        path.mkdir(parents=True)
        (path / "workspace.yaml").write_text(
            "schema_version: 2\n"
            "workspace:\n"
            f"  id: '{workspace_id}'\n"
            "  name: 'serving-workspace'\n"
            "repositories:\n",
            encoding="utf-8",
        )

    def write_task(
        self,
        path: Path,
        task_id: str,
        *,
        workspace: Path | None = None,
        include_workspace_id: bool = True,
        runtime: bool = False,
    ) -> None:
        path.mkdir(parents=True)
        if workspace is None:
            marker = "agent_task: 1\n"
            workspace_fields = ""
            objective_heading = "Current objective"
        else:
            marker = "workspace_task: 1\n"
            workspace_fields = (
                ("workspace_id: workspace-1\n" if include_workspace_id else "")
                + "workspace: serving-workspace\n"
                + f"workspace_path: '{workspace}'\n"
            )
            objective_heading = "Goal"
        runtime_fields = (
            "runtime_host: gpu-box\ntmux_session: serving-run\n" if runtime else ""
        )
        (path / "README.md").write_text(
            "---\n"
            + marker
            + f"id: {task_id}\n"
            + f"title: {path.name}\n"
            + "status: active\n"
            + workspace_fields
            + "created: 2026-09-01\nupdated: 2026-09-02\n"
            + "last_used_at: 2026-09-02T10:00:00+00:00\n"
            + runtime_fields
            + "---\n\n"
            + f"## {objective_heading}\n\nMeasure request latency.\n\n"
            + "## Current state\n\nReady to run.\n\n"
            + "## Immediate next task\n\nRun the first sample.\n",
            encoding="utf-8",
        )

    def json_result(self, result: subprocess.CompletedProcess[str]) -> dict:
        return json.loads(result.stdout)

    def test_registers_separate_workspace_and_task_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "state" / "catalog.sqlite3"
            workspace = root / "workspace"
            task = root / "execution" / "latency"
            standalone = root / "personal"
            self.write_workspace(workspace)
            self.write_task(task, "task-1", workspace=workspace, runtime=True)
            self.write_task(standalone, "task-2")

            self.run_catalog(database, "register", "--path", str(workspace))
            registered = self.json_result(
                self.run_catalog(database, "register", "--path", str(task))
            )["records"][0]
            self.run_catalog(database, "register", "--path", str(standalone))

            self.assertEqual(registered["record_type"], "task")
            self.assertEqual(registered["kind"], "workspace-task")
            self.assertEqual(registered["workspace_id"], "workspace-1")
            self.assertEqual(registered["workspace_name"], "serving-workspace")
            self.assertNotIn("tss_target", registered)
            self.assertEqual(registered["objective"], "Measure request latency.")

            payload = self.json_result(
                self.run_catalog(database, "list", "--format", "json")
            )
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(len(payload["records"]), 3)
            expected_fields = {
                "record_type",
                "kind",
                "id",
                "name",
                "title",
                "workspace_id",
                "workspace_name",
                "path",
                "present",
                "status",
                "created",
                "updated",
                "last_used",
                "objective",
                "current_state",
                "next_task",
                "git_root",
                "git_remote",
                "git_commit",
                "last_seen",
            }
            self.assertTrue(
                all(set(record) == expected_fields for record in payload["records"])
            )

            with sqlite3.connect(database) as connection:
                counts = {
                    table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in (
                        "workspaces",
                        "workspace_locations",
                        "tasks",
                        "task_locations",
                    )
                }
            self.assertEqual(
                counts,
                {
                    "workspaces": 1,
                    "workspace_locations": 1,
                    "tasks": 2,
                    "task_locations": 2,
                },
            )

            human = self.run_catalog(database, "list", "-H").stdout
            self.assertIn("Catalog: 1 workspaces, 2 tasks", human)
            self.assertIn("[active] latency", human)
            self.assertIn("Kind: workspace task | Workspace: serving-workspace", human)
            self.assertNotIn("Session:", human)
            self.assertIn(f"Path: {task.resolve()}", human)

    def test_same_task_id_can_have_multiple_locations_and_filters_run_in_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            first = root / "first"
            second = root / "second"
            self.write_task(first, "shared-task")
            shutil.copytree(first, second)
            self.run_catalog(database, "register", "--path", str(first))
            self.run_catalog(database, "register", "--path", str(second))

            records = self.json_result(
                self.run_catalog(
                    database,
                    "list",
                    "--format",
                    "json",
                    "--kind",
                    "agent-task",
                )
            )["records"]
            self.assertEqual([record["id"] for record in records], ["shared-task"] * 2)
            self.assertEqual(
                {Path(record["path"]) for record in records},
                {first.resolve(), second.resolve()},
            )

            module = load_catalog_module()
            normalized = " ".join(module.DISCOVERY_SELECT.upper().split())
            self.assertNotIn("?", module.DISCOVERY_SELECT)
            self.assertNotIn("{", module.DISCOVERY_SELECT)
            self.assertNotIn(" WHERE ", f" {normalized} ")
            self.assertNotIn(" ORDER BY ", f" {normalized} ")

    def test_default_database_uses_runtime_harness_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / "task"
            harness_home = root / "custom-harness"
            self.write_task(task, "task-1")
            environment = dict(os.environ)
            environment["AGENT_HARNESS_HOME"] = str(harness_home)
            result = subprocess.run(
                [sys.executable, str(CATALOG), "register", "--path", str(task)],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (harness_home / "state/task-catalog/catalog.sqlite3").is_file()
            )

    def test_legacy_workspace_task_infers_id_from_local_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            workspace = root / "workspace"
            task = root / "legacy-task"
            self.write_workspace(workspace)
            self.write_task(
                task,
                "legacy-task-id",
                workspace=workspace,
                include_workspace_id=False,
            )

            record = self.json_result(
                self.run_catalog(database, "register", "--path", str(task))
            )["records"][0]
            self.assertEqual(record["workspace_id"], "workspace-1")
            self.assertEqual(record["workspace_name"], "serving-workspace")
            all_records = self.json_result(
                self.run_catalog(database, "export")
            )["records"]
            self.assertEqual(
                {entry["record_type"] for entry in all_records},
                {"workspace", "task"},
            )

    def test_legacy_workspace_without_id_uses_normalized_git_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "workspace.yaml").write_text(
                "schema_version: 1\n"
                "workspace:\n"
                "  name: 'legacy-workspace'\n"
                "repositories:\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(workspace)], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "remote",
                    "add",
                    "origin",
                    "git@example.com:team/workspace.git",
                ],
                check=True,
            )

            record = self.json_result(
                self.run_catalog(database, "register", "--path", str(workspace))
            )["records"][0]
            self.assertTrue(record["id"].startswith("legacy-origin:"))

            module = load_catalog_module()
            self.assertEqual(
                module.normalized_git_remote("git@example.com:team/workspace.git"),
                module.normalized_git_remote("https://example.com/team/workspace.git"),
            )

    def test_schema_two_migration_preserves_context_and_drops_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            task = root / "task"
            self.write_task(task, "task-1", runtime=True)
            self.run_catalog(database, "register", "--path", str(task))
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE sessions(id INTEGER PRIMARY KEY, runtime_host TEXT)"
                )
                connection.execute("INSERT INTO sessions(runtime_host) VALUES ('old')")
                connection.execute(
                    "UPDATE catalog_metadata SET value = '1' WHERE key = 'schema_version'"
                )
                connection.commit()

            payload = self.json_result(
                self.run_catalog(database, "list", "--format", "json")
            )
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["records"][0]["id"], "task-1")
            with sqlite3.connect(database) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                version = connection.execute(
                    "SELECT value FROM catalog_metadata WHERE key = 'schema_version'"
                ).fetchone()[0]
            self.assertNotIn("sessions", tables)
            self.assertEqual(version, "2")

    def test_reconcile_registers_recognized_folders_and_marks_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            scan_root = root / "documents"
            scan_root.mkdir()
            workspace = scan_root / "workspace"
            task = scan_root / "task"
            ignored = scan_root / ".worktrees" / "ignored-task"
            self.write_workspace(workspace)
            self.write_task(task, "task-1")
            self.write_task(ignored, "ignored")

            records = self.json_result(
                self.run_catalog(
                    database,
                    "reconcile",
                    str(scan_root),
                    "--format",
                    "json",
                )
            )["records"]
            self.assertEqual({record["id"] for record in records}, {"workspace-1", "task-1"})

            shutil.rmtree(task)
            records = self.json_result(
                self.run_catalog(
                    database,
                    "reconcile",
                    str(scan_root),
                    "--format",
                    "json",
                )
            )["records"]
            missing = next(record for record in records if record["id"] == "task-1")
            self.assertFalse(missing["present"])

    def test_records_git_details_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            task = root / "git-task"
            self.write_task(task, "task-1")
            subprocess.run(["git", "init", "-q", "-b", "main", str(task)], check=True)
            subprocess.run(["git", "-C", str(task), "add", "README.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(task),
                    "-c",
                    "user.name=Test User",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-q",
                    "-m",
                    "initial",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(task), "remote", "add", "origin", "ssh://example/task.git"],
                check=True,
            )

            record = self.json_result(
                self.run_catalog(database, "register", "--path", str(task))
            )["records"][0]
            self.assertEqual(Path(record["git_root"]), task.resolve())
            self.assertEqual(record["git_remote"], "ssh://example/task.git")
            self.assertEqual(len(record["git_commit"]), 40)

    def test_concurrent_registration_uses_one_database_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "catalog.sqlite3"
            tasks = []
            for index in range(8):
                task = root / f"task-{index}"
                self.write_task(task, f"id-{index}")
                tasks.append(task)

            def register(task: Path) -> subprocess.CompletedProcess[str]:
                return self.run_catalog(database, "register", "--path", str(task))

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(register, tasks))
            self.assertTrue(all(result.returncode == 0 for result in results))
            records = self.json_result(
                self.run_catalog(database, "list", "--format", "json")
            )["records"]
            self.assertEqual({record["id"] for record in records}, {f"id-{i}" for i in range(8)})


if __name__ == "__main__":
    unittest.main()
