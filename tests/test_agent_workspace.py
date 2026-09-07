from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HYDRATE_WORKSPACE = (
    REPO_ROOT
    / "agent-skills"
    / "agent-workspace"
    / "scripts"
    / "hydrate_workspace.py"
)
START_TASK = (
    REPO_ROOT
    / "agent-skills"
    / "agent-workspace"
    / "scripts"
    / "start_workspace_task.py"
)
LIST_TASKS = (
    REPO_ROOT
    / "agent-skills"
    / "agent-workspace"
    / "scripts"
    / "list_workspace_tasks.py"
)
TASK_CATALOG = REPO_ROOT / "scripts" / "task-catalog.py"
AGENT_WORKSPACE_CLI = REPO_ROOT / "scripts" / "agent-workspace.py"
START_SESSION = (
    REPO_ROOT
    / "agent-skills"
    / "task-session"
    / "scripts"
    / "start_task_session.py"
)
SET_TASK_STATE = (
    REPO_ROOT
    / "agent-skills"
    / "task-session"
    / "scripts"
    / "set_task_state.py"
)
class AgentWorkspaceTaskTests(unittest.TestCase):
    def catalog_env(self, root: Path) -> dict[str, str]:
        harness_home = root / "harness-home"
        bin_dir = harness_home / "bin"
        bin_dir.mkdir(parents=True)
        installed = bin_dir / "task-catalog"
        shutil.copy2(TASK_CATALOG, installed)
        installed.chmod(0o755)
        env = os.environ.copy()
        env["AGENT_HARNESS_HOME"] = str(harness_home)
        return env

    def register(self, env: dict[str, str], path: Path) -> dict[str, object]:
        result = subprocess.run(
            [str(Path(env["AGENT_HARNESS_HOME"]) / "bin" / "task-catalog"),
             "register", "--path", str(path), "--format", "json"],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        return json.loads(result.stdout)

    def run_script(
        self,
        script: Path,
        *args: str,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if check and result.returncode != 0:
            self.fail(
                f"{script.name} failed with {result.returncode}: {result.stderr}"
            )
        return result

    def prepare_workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "workspace.yaml").write_text(
            "schema_version: 2\n"
            "workspace:\n"
            "  id: 'workspace-demo-id'\n"
            "  name: 'demo-workspace'\n"
            "repositories:\n",
            encoding="utf-8",
        )
        (workspace / "AGENTS.md").write_text(
            "# Workspace instructions\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(workspace)], check=True
        )
        return workspace

    def test_hydrated_workspace_includes_workflow_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            seed = root / "seed"
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(seed)], check=True
            )
            (seed / "README.md").write_text("# Seed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(seed), "add", "README.md"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(seed),
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
            remote = root / "remote.git"
            subprocess.run(
                ["git", "clone", "-q", "--bare", str(seed), str(remote)],
                check=True,
            )
            destination = root / "destination"
            destination.mkdir()
            result = self.run_script(
                HYDRATE_WORKSPACE,
                "--name",
                "demo",
                "--destination",
                str(destination),
                "--repo",
                f"app|{remote}|main|active",
                env=env,
            )
            workspace = Path(result.stdout.strip())
            self.assertFalse((workspace / "tasks").exists())
            self.assertTrue((workspace / "workflow" / "README.md").is_file())
            self.assertTrue((workspace / "app").is_dir())
            manifest = (workspace / "workspace.yaml").read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", manifest)
            self.assertIn("  id:", manifest)
            self.assertNotIn(
                "/tasks/", (workspace / ".gitignore").read_text(encoding="utf-8")
            )
            self.assertIn(
                "start-task <task-name>",
                (workspace / "README.md").read_text(encoding="utf-8"),
            )
            agents_md = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(
                "does not create\nrepository worktrees",
                agents_md,
            )
            self.assertIn(
                "write generated output to the current task's\nexecution folder",
                agents_md,
            )
            self.assertIn(
                "Execution output stays in execution-notes",
                (workspace / "README.md").read_text(encoding="utf-8"),
            )
            (workspace / "task-history.json").write_text(
                json.dumps({"schema_version": 1, "hosts": {}}) + "\n",
                encoding="utf-8",
            )

            portable = root / "portable-copy"
            rehydrated = self.run_script(
                HYDRATE_WORKSPACE,
                "--rehydrate-from",
                str(workspace / "workspace.yaml"),
                "--destination",
                str(portable),
                env=env,
            )
            self.assertEqual(Path(rehydrated.stdout.strip()), portable.resolve())
            self.assertTrue((portable / "app" / ".git").exists())
            self.assertEqual(
                (portable / "workspace.yaml").read_text(encoding="utf-8"),
                manifest,
            )
            self.assertFalse((portable / "task-history.json").exists())
            self.assertTrue((workspace / "task-history.json").is_file())
            repeated = self.run_script(
                HYDRATE_WORKSPACE,
                "--rehydrate-from",
                str(workspace / "workspace.yaml"),
                "--destination",
                str(portable),
                env=env,
            )
            self.assertEqual(Path(repeated.stdout.strip()), portable.resolve())
            records = json.loads(
                subprocess.run(
                    [str(Path(env["AGENT_HARNESS_HOME"]) / "bin" / "task-catalog"),
                     "list", "--kind", "workspace", "--format", "json"],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                ).stdout
            )["records"]
            self.assertEqual(
                {Path(record["path"]) for record in records},
                {workspace.resolve(), portable.resolve()},
            )
            self.assertEqual(len({record["id"] for record in records}), 1)

            catalog = Path(env["AGENT_HARNESS_HOME"]) / "bin" / "task-catalog"
            catalog.unlink()
            partial_parent = root / "partial-parent"
            partial_parent.mkdir()
            partial_init = self.run_script(
                AGENT_WORKSPACE_CLI,
                "init",
                "--name",
                "partial-init",
                "--destination",
                str(partial_parent),
                "--repo",
                f"app|{remote}|main|active",
                "--format",
                "json",
                check=False,
                env=env,
            )
            self.assertEqual(partial_init.returncode, 2)
            partial_init_payload = json.loads(partial_init.stdout)
            self.assertEqual(partial_init_payload["outcome"], "partial")
            self.assertTrue(
                Path(partial_init_payload["workspace"], "workspace.yaml").is_file()
            )

            partial_rehydrate_path = root / "partial-rehydrate"
            partial_rehydrate = self.run_script(
                AGENT_WORKSPACE_CLI,
                "rehydrate",
                "--manifest",
                str(workspace / "workspace.yaml"),
                "--destination",
                str(partial_rehydrate_path),
                "--format",
                "json",
                check=False,
                env=env,
            )
            self.assertEqual(partial_rehydrate.returncode, 2)
            self.assertEqual(
                json.loads(partial_rehydrate.stdout)["outcome"], "partial"
            )
            self.assertTrue((partial_rehydrate_path / "workspace.yaml").is_file())

    def test_creates_minimal_task_record_and_discovers_default_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            self.register(env, workspace)
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps({"execution_root": str(execution_root)}), encoding="utf-8"
            )

            result = self.run_script(
                START_TASK,
                "--workspace",
                str(workspace),
                "--name",
                "model-serving",
                "--objective",
                "Measure serving latency.",
                "--config",
                str(config),
                "--format",
                "json",
                env=env,
            )
            payload = json.loads(result.stdout)
            task = execution_root / "model-serving"
            self.assertEqual(
                Path(payload["execution_folder"]), task.resolve()
            )
            self.assertTrue((task / "README.md").is_file())
            self.assertEqual(
                [entry.name for entry in task.iterdir()],
                ["README.md"],
            )
            self.assertFalse((workspace / "tasks").exists())
            task_index = workspace / ".git" / "agent-workspace" / "task-paths.json"
            self.assertFalse(task_index.exists())
            self.assertFalse((workspace / "task-history.json").exists())
            self.assertFalse(any(workspace.glob("*-worktree/model-serving")))

            readme = (task / "README.md").read_text(encoding="utf-8")
            self.assertIn("workspace_task: 1", readme)
            self.assertIn("workspace: demo-workspace", readme)
            self.assertNotIn("workspace_path:", readme)
            self.assertIn("Measure serving latency.", readme)

            repeated = self.run_script(
                START_TASK,
                "--workspace",
                str(workspace),
                "--name",
                "model-serving",
                "--config",
                str(config),
                check=False,
                env=env,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to overwrite", repeated.stderr)

            alternate_parent = root / "alternate"
            alternate_parent.mkdir()
            alternate_task = alternate_parent / "custom-location"
            override = json.loads(
                self.run_script(
                    START_TASK,
                    "--workspace",
                    str(workspace),
                    "--name",
                    "custom-location",
                    "--config",
                    str(config),
                    "--execution-folder",
                    str(alternate_task),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(Path(override["execution_folder"]), alternate_task.resolve())
            self.assertTrue(alternate_task.is_dir())
            self.assertFalse((execution_root / "custom-location").exists())

            discovered = json.loads(
                self.run_script(
                    LIST_TASKS,
                    "--workspace",
                    str(workspace),
                    "--config",
                    str(config),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(
                {task["task_name"] for task in discovered["tasks"]},
                {"custom-location", "model-serving"},
            )
            self.assertTrue(
                all(task["last_used_at"] for task in discovered["tasks"])
            )
            self.assertEqual(discovered["missing_paths"], [])
            self.assertEqual(
                {Path(task["path"]) for task in discovered["tasks"]},
                {alternate_task.resolve(), task.resolve()},
            )

            portable_workspace = root / "portable-workspace"
            portable_workspace.mkdir()
            shutil.copy2(
                workspace / "workspace.yaml",
                portable_workspace / "workspace.yaml",
            )
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(portable_workspace)],
                check=True,
            )
            self.register(env, portable_workspace)
            portable_discovery = json.loads(
                self.run_script(
                    LIST_TASKS,
                    "--workspace",
                    str(portable_workspace),
                    "--config",
                    str(config),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(
                {record["task_name"] for record in portable_discovery["tasks"]},
                {"custom-location", "model-serving"},
            )

            default_readme = task / "README.md"
            default_readme.write_text(
                default_readme.read_text(encoding="utf-8").replace(
                    "status: active", "status: done", 1
                ),
                encoding="utf-8",
            )
            self.register(env, task)
            active = json.loads(
                self.run_script(
                    LIST_TASKS,
                    "--workspace",
                    str(workspace),
                    "--config",
                    str(config),
                    "--status",
                    "active",
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(
                [record["task_name"] for record in active["tasks"]],
                ["custom-location"],
            )

    def test_catalog_keeps_two_local_locations_for_one_portable_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            self.register(env, workspace)
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps({"execution_root": str(execution_root)}), encoding="utf-8"
            )
            first = json.loads(
                self.run_script(
                    START_TASK,
                    "--workspace", str(workspace), "--name", "portable-task",
                    "--config", str(config), "--format", "json",
                    env=env,
                ).stdout
            )
            original = Path(first["execution_folder"])
            second_location = root / "second-device-copy"
            shutil.copytree(original, second_location)
            self.register(env, second_location)

            listed = json.loads(
                self.run_script(
                    LIST_TASKS, "--workspace", str(workspace),
                    "--format", "json",
                    env=env,
                ).stdout
            )["tasks"]
            self.assertEqual(len(listed), 2)
            self.assertEqual({task["id"] for task in listed}, {first["task_id"]})
            self.assertEqual(
                {Path(task["path"]) for task in listed},
                {original.resolve(), second_location.resolve()},
            )
            self.assertFalse((workspace / "task-history.json").exists())
            self.assertFalse(
                (workspace / ".git" / "agent-workspace" / "task-paths.json").exists()
            )

    def test_public_cli_preserves_registered_task_when_session_start_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            self.register(env, workspace)
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps({"execution_root": str(execution_root)}),
                encoding="utf-8",
            )

            result = self.run_script(
                AGENT_WORKSPACE_CLI,
                "start-task",
                "--workspace",
                str(workspace),
                "--name",
                "no-runtime-host",
                "--config",
                str(config),
                "--format",
                "json",
                check=False,
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["session_started"])
            task_path = Path(payload["task"]["execution_folder"])
            self.assertTrue((task_path / "README.md").is_file())
            self.assertIn("TSS host label is unresolved", payload["session_error"])

            listed = json.loads(
                self.run_script(
                    AGENT_WORKSPACE_CLI,
                    "list-tasks",
                    "--workspace",
                    str(workspace),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(
                [task["task_name"] for task in listed["tasks"]],
                ["no-runtime-host"],
            )

    def test_legacy_workspace_id_is_resolved_from_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            remote = root / "workspace-origin.git"
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            workspace_ids: set[str] = set()
            workspaces: list[Path] = []
            for name in ("legacy-a", "legacy-b"):
                workspace = root / name
                workspace.mkdir()
                (workspace / "workspace.yaml").write_text(
                    "schema_version: 1\n"
                    "workspace:\n"
                    "  name: 'legacy-demo'\n"
                    "repositories:\n",
                    encoding="utf-8",
                )
                subprocess.run(
                    ["git", "init", "-q", "-b", "main", str(workspace)], check=True
                )
                subprocess.run(
                    ["git", "-C", str(workspace), "remote", "add", "origin", str(remote)],
                    check=True,
                )
                registered = self.register(env, workspace)
                workspace_ids.add(registered["records"][0]["id"])
                workspaces.append(workspace)
            self.assertEqual(len(workspace_ids), 1)
            workspace_id = workspace_ids.pop()

            task = root / "legacy-task"
            task.mkdir()
            (task / "README.md").write_text(
                f"""---
workspace_task: 1
id: legacy-task-id
task_name: legacy-task
title: legacy-task
status: active
workspace: legacy-demo
workspace_id: {workspace_id}
created: 2026-09-01
updated: 2026-09-01
last_used_at: 2026-09-01T00:00:00+00:00
---

# legacy-task
""",
                encoding="utf-8",
            )
            self.register(env, task)
            listed = json.loads(
                self.run_script(
                    LIST_TASKS,
                    "--workspace",
                    str(workspaces[1]),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            self.assertEqual(
                [record["task_name"] for record in listed["tasks"]],
                ["legacy-task"],
            )

    def test_start_task_uses_catalog_id_for_legacy_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            manifest = workspace / "workspace.yaml"
            lines = manifest.read_text(encoding="utf-8").splitlines()
            manifest.write_text(
                "\n".join(line for line in lines if not line.strip().startswith("id:"))
                + "\n",
                encoding="utf-8",
            )
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps({"execution_root": str(execution_root)}),
                encoding="utf-8",
            )

            result = json.loads(
                self.run_script(
                    START_TASK,
                    "--workspace",
                    str(workspace),
                    "--name",
                    "legacy-start",
                    "--config",
                    str(config),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )

            self.assertTrue(result["catalog_registered"])
            self.assertTrue(str(result["workspace_id"]).startswith("legacy-"))
            readme = (execution_root / "legacy-start" / "README.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(f"workspace_id: '{result['workspace_id']}'", readme)

    def test_public_cli_returns_partial_when_task_registration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            self.register(env, workspace)
            catalog = Path(env["AGENT_HARNESS_HOME"]) / "bin" / "task-catalog"
            catalog.unlink()
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps({"execution_root": str(execution_root)}),
                encoding="utf-8",
            )

            result = self.run_script(
                AGENT_WORKSPACE_CLI,
                "start-task",
                "--workspace",
                str(workspace),
                "--name",
                "catalog-failure",
                "--config",
                str(config),
                "--tss-host",
                "local",
                "--format",
                "json",
                check=False,
                env=env,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["outcome"], "partial")
            self.assertFalse(payload["session_started"])
            self.assertFalse(payload["task"]["catalog_registered"])
            self.assertTrue(
                Path(payload["task"]["execution_folder"], "README.md").is_file()
            )
            self.assertIn("registration failed", payload["session_error"])

    @unittest.skipUnless(shutil.which("tmux"), "tmux is required")
    def test_workspace_task_can_start_isolated_tmux_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = self.catalog_env(root)
            workspace = self.prepare_workspace(root)
            self.register(env, workspace)
            execution_root = root / "execution-notes"
            execution_root.mkdir()
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "execution_root": str(execution_root),
                        "task_runtime": {"tss": {"host_alias": "local"}},
                    }
                ),
                encoding="utf-8",
            )
            task_payload = json.loads(
                self.run_script(
                    START_TASK,
                    "--workspace",
                    str(workspace),
                    "--name",
                    "model-serving",
                    "--config",
                    str(config),
                    "--format",
                    "json",
                    env=env,
                ).stdout
            )
            runtime_workspace = root / "workspace-on-this-host"
            runtime_workspace.mkdir()
            shutil.copy2(
                workspace / "workspace.yaml",
                runtime_workspace / "workspace.yaml",
            )

            tmux_tmp = root / "tmux"
            tmux_tmp.mkdir()
            env["TMUX_TMPDIR"] = str(tmux_tmp)
            socket_name = f"ws-{uuid.uuid4().hex[:6]}"
            try:
                session_payload = json.loads(
                    self.run_script(
                        START_SESSION,
                        "--task-dir",
                        task_payload["execution_folder"],
                        "--config",
                        str(config),
                        "--workspace",
                        str(runtime_workspace),
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertEqual(session_payload["tss_target"], "local:model-serving")
                self.assertTrue(session_payload["created"])
                option = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "show-options",
                        "-v",
                        "-t",
                        "model-serving",
                        "@agent_workspace",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(option.stdout.strip(), "demo-workspace")
                pane_path = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "display-message",
                        "-p",
                        "-t",
                        "model-serving",
                        "#{pane_current_path}",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(
                    Path(pane_path.stdout.strip()).resolve(),
                    runtime_workspace.resolve(),
                )
                for option_name, expected in (
                    ("@agent_task_path", task_payload["execution_folder"]),
                    ("@agent_workspace_path", str(runtime_workspace.resolve())),
                ):
                    value = subprocess.run(
                        [
                            "tmux",
                            "-L",
                            socket_name,
                            "show-options",
                            "-v",
                            "-t",
                            "model-serving",
                            option_name,
                        ],
                        check=True,
                        text=True,
                        capture_output=True,
                        env=env,
                    )
                    self.assertEqual(value.stdout.strip(), expected)

                waiting = json.loads(
                    self.run_script(
                        SET_TASK_STATE,
                        "--task-dir",
                        task_payload["execution_folder"],
                        "--status",
                        "waiting",
                        "--summary",
                        "Waiting for capacity.",
                        "--next-step",
                        "Resume when capacity is available.",
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertTrue(waiting["session_marked"])
                task_text = Path(
                    task_payload["execution_folder"], "README.md"
                ).read_text(encoding="utf-8")
                self.assertIn("status: waiting", task_text)
                self.assertIn("state_changed_at:", task_text)
                self.assertIn("Resume when capacity is available.", task_text)
                state_option = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "show-options",
                        "-v",
                        "-t",
                        "model-serving",
                        "@agent_task_status",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(state_option.stdout.strip(), "waiting")
                discovered = json.loads(
                    self.run_script(
                        LIST_TASKS,
                        "--workspace",
                        str(workspace),
                        "--config",
                        str(config),
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertEqual(
                    discovered["tasks"][0]["tss_target"],
                    "local:model-serving",
                )
            finally:
                subprocess.run(
                    ["tmux", "-L", socket_name, "kill-server"],
                    check=False,
                    text=True,
                    capture_output=True,
                    env=env,
                )


if __name__ == "__main__":
    unittest.main()
