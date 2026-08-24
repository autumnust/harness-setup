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
HYDRATE_TASK = (
    REPO_ROOT / "agent-skills" / "agent-task" / "scripts" / "hydrate_task.py"
)
DISCOVER_TASKS = (
    REPO_ROOT / "agent-skills" / "agent-task" / "scripts" / "discover_tasks.py"
)
START_SESSION = (
    REPO_ROOT
    / "agent-skills"
    / "task-session"
    / "scripts"
    / "start_task_session.py"
)
FINISH_TASK = (
    REPO_ROOT
    / "agent-skills"
    / "task-session"
    / "scripts"
    / "finish_task.py"
)
SET_TASK_STATE = (
    REPO_ROOT
    / "agent-skills"
    / "task-session"
    / "scripts"
    / "set_task_state.py"
)


class TaskFinishWithoutSessionTests(unittest.TestCase):
    def test_filesystem_completion_succeeds_without_a_recorded_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(
                [
                    sys.executable,
                    str(HYDRATE_TASK),
                    "--name",
                    "offline-task",
                    "--objective",
                    "Complete after the session is gone",
                    "--destination",
                    str(root),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(FINISH_TASK),
                    "--task-dir",
                    str(root / "offline-task"),
                    "--outcome",
                    "The requested work is complete.",
                    "--format",
                    "json",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "done")
            self.assertFalse(payload["session_marked"])
            self.assertIn("no recorded tmux session", payload["session_warning"])
            readme = (root / "offline-task" / "README.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("status: done", readme)
            self.assertIn("## Outcome", readme)


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class TaskSessionTests(unittest.TestCase):
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

    def test_agent_task_session_uses_existing_folder_and_reports_to_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_script(
                HYDRATE_TASK,
                "--name",
                "personal finance",
                "--objective",
                "Organize tax records",
                "--destination",
                str(root),
            )
            task = root / "personal finance"
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {"task_runtime": {"tss": {"host_alias": "local"}}}
                ),
                encoding="utf-8",
            )
            tmux_tmp = root / "tmux"
            tmux_tmp.mkdir()
            env = os.environ.copy()
            env["TMUX_TMPDIR"] = str(tmux_tmp)
            socket_name = f"at-{uuid.uuid4().hex[:6]}"
            try:
                first = json.loads(
                    self.run_script(
                        START_SESSION,
                        "--task-dir",
                        str(task),
                        "--config",
                        str(config),
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertTrue(first["created"])
                self.assertEqual(first["session_name"], "personal-finance")
                self.assertEqual(first["tss_target"], "local:personal-finance")

                second = json.loads(
                    self.run_script(
                        START_SESSION,
                        "--task-dir",
                        str(task),
                        "--config",
                        str(config),
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertFalse(second["created"])

                text_result = self.run_script(
                    START_SESSION,
                    "--task-dir",
                    str(task),
                    "--config",
                    str(config),
                    "--tmux-socket",
                    socket_name,
                    env=env,
                )
                self.assertIn("Connect: tss local:personal-finance", text_result.stdout)

                readme = (task / "README.md").read_text(encoding="utf-8")
                self.assertIn("runtime_host: local", readme)
                self.assertIn("tmux_session: personal-finance", readme)

                discovered = json.loads(
                    self.run_script(
                        DISCOVER_TASKS, str(root), "--format", "json"
                    ).stdout
                )["tasks"][0]
                self.assertEqual(discovered["runtime_host"], "local")
                self.assertEqual(discovered["tmux_session"], "personal-finance")
                self.assertEqual(discovered["tss_target"], "local:personal-finance")

                task_id = discovered["id"]
                option = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "show-options",
                        "-v",
                        "-t",
                        "personal-finance",
                        "@agent_task_id",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(option.stdout.strip(), task_id)

                status_option = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "show-options",
                        "-v",
                        "-t",
                        "personal-finance",
                        "@agent_task_status",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(status_option.stdout.strip(), "active")

                finished = json.loads(
                    self.run_script(
                        FINISH_TASK,
                        "--task-dir",
                        str(task),
                        "--outcome",
                        "Tax records are organized and verified.",
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertEqual(finished["status"], "done")
                self.assertTrue(finished["session_marked"])

                finished_readme = (task / "README.md").read_text(encoding="utf-8")
                self.assertIn("status: done", finished_readme)
                self.assertIn("completed:", finished_readme)
                self.assertIn("## Outcome", finished_readme)
                self.assertIn(
                    "Tax records are organized and verified.", finished_readme
                )
                self.assertTrue(
                    subprocess.run(
                        [
                            "tmux",
                            "-L",
                            socket_name,
                            "has-session",
                            "-t",
                            "personal-finance",
                        ],
                        check=False,
                        text=True,
                        capture_output=True,
                        env=env,
                    ).returncode
                    == 0
                )
                for option_name, expected in (
                    ("@agent_task_status", "done"),
                    ("@agent_task_finished_at", finished["completed"]),
                ):
                    value = subprocess.run(
                        [
                            "tmux",
                            "-L",
                            socket_name,
                            "show-options",
                            "-v",
                            "-t",
                            "personal-finance",
                            option_name,
                        ],
                        check=True,
                        text=True,
                        capture_output=True,
                        env=env,
                    )
                    self.assertEqual(value.stdout.strip(), expected)

                finished_discovery = json.loads(
                    self.run_script(
                        DISCOVER_TASKS, str(root), "--format", "json"
                    ).stdout
                )["tasks"][0]
                self.assertEqual(finished_discovery["status"], "done")

                resumed = json.loads(
                    self.run_script(
                        SET_TASK_STATE,
                        "--task-dir",
                        str(task),
                        "--status",
                        "active",
                        "--summary",
                        "A follow-up verification was requested.",
                        "--next-step",
                        "Verify the additional records.",
                        "--tmux-socket",
                        socket_name,
                        "--format",
                        "json",
                        env=env,
                    ).stdout
                )
                self.assertTrue(resumed["session_marked"])
                resumed_readme = (task / "README.md").read_text(encoding="utf-8")
                self.assertIn("status: active", resumed_readme)
                self.assertNotIn("completed:", resumed_readme)
                self.assertNotIn("## Outcome", resumed_readme)
                self.assertIn("Verify the additional records.", resumed_readme)
                finished_option = subprocess.run(
                    [
                        "tmux",
                        "-L",
                        socket_name,
                        "show-options",
                        "-v",
                        "-t",
                        "personal-finance",
                        "@agent_task_finished_at",
                    ],
                    check=False,
                    text=True,
                    capture_output=True,
                    env=env,
                )
                self.assertNotEqual(finished_option.returncode, 0)

                self.run_script(
                    HYDRATE_TASK,
                    "--name",
                    "another task",
                    "--objective",
                    "Verify session-name collision handling",
                    "--destination",
                    str(root),
                )
                collision = self.run_script(
                    START_SESSION,
                    "--task-dir",
                    str(root / "another task"),
                    "--tss-host",
                    "local",
                    "--session-name",
                    "personal-finance",
                    "--tmux-socket",
                    socket_name,
                    check=False,
                    env=env,
                )
                self.assertNotEqual(collision.returncode, 0)
                self.assertIn("another or unrecorded task", collision.stderr)
                other_readme = (root / "another task" / "README.md").read_text(
                    encoding="utf-8"
                )
                self.assertNotIn("runtime_host:", other_readme)
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
