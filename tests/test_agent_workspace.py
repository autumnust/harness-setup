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
            self.assertIn(
                "does not create\nrepository worktrees",
                (workspace / "AGENTS.md").read_text(encoding="utf-8"),
            )

            portable = root / "portable-copy"
            rehydrated = self.run_script(
                HYDRATE_WORKSPACE,
                "--rehydrate-from",
                str(workspace / "workspace.yaml"),
                "--destination",
                str(portable),
            )
            self.assertEqual(Path(rehydrated.stdout.strip()), portable.resolve())
            self.assertTrue((portable / "app" / ".git").exists())
            self.assertEqual(
                (portable / "workspace.yaml").read_text(encoding="utf-8"),
                manifest,
            )
            repeated = self.run_script(
                HYDRATE_WORKSPACE,
                "--rehydrate-from",
                str(workspace / "workspace.yaml"),
                "--destination",
                str(portable),
            )
            self.assertEqual(Path(repeated.stdout.strip()), portable.resolve())

    def test_creates_minimal_task_record_and_discovers_default_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.prepare_workspace(root)
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
            task_index = (
                workspace / ".git" / "agent-workspace" / "task-paths.json"
            )
            self.assertTrue(task_index.is_file())
            self.assertFalse(any(workspace.glob("*-worktree/model-serving")))

            readme = (task / "README.md").read_text(encoding="utf-8")
            self.assertIn("workspace_task: 1", readme)
            self.assertIn("workspace: demo-workspace", readme)
            self.assertIn(f"workspace_path: {workspace.resolve()}", readme)
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
                ).stdout
            )
            self.assertEqual(
                [task["task_name"] for task in discovered["tasks"]],
                ["custom-location", "model-serving"],
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
            portable_discovery = json.loads(
                self.run_script(
                    LIST_TASKS,
                    "--workspace",
                    str(portable_workspace),
                    "--config",
                    str(config),
                    "--format",
                    "json",
                ).stdout
            )
            self.assertEqual(
                [record["task_name"] for record in portable_discovery["tasks"]],
                ["model-serving"],
            )

            default_readme = task / "README.md"
            default_readme.write_text(
                default_readme.read_text(encoding="utf-8").replace(
                    "status: active", "status: done", 1
                ),
                encoding="utf-8",
            )
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
                ).stdout
            )
            self.assertEqual(
                [record["task_name"] for record in active["tasks"]],
                ["custom-location"],
            )

    @unittest.skipUnless(shutil.which("tmux"), "tmux is required")
    def test_workspace_task_can_start_isolated_tmux_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.prepare_workspace(root)
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
            env = os.environ.copy()
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
