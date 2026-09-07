from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_CATALOG = REPO_ROOT / "scripts" / "task-catalog.py"
RECOVER = (
    REPO_ROOT
    / "agent-skills"
    / "crash-recovery"
    / "scripts"
    / "recover_task_sessions.py"
)


def task_readme(task_id: str, title: str) -> str:
    return f"""---
agent_task: 1
id: {task_id}
title: {title}
status: active
runtime_host: local
tmux_session: {title}
created: 2026-09-01
updated: 2026-09-02
last_used_at: 2026-09-02T00:00:00+00:00
---

# {title}

## Goal

Test recovery.
"""


class CrashRecoveryTests(unittest.TestCase):
    def test_report_reads_catalog_without_scanning_neighbor_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness_home = root / "harness-home"
            bin_dir = harness_home / "bin"
            bin_dir.mkdir(parents=True)
            catalog = bin_dir / "task-catalog"
            shutil.copy2(TASK_CATALOG, catalog)
            catalog.chmod(0o755)
            env = os.environ.copy()
            env["AGENT_HARNESS_HOME"] = str(harness_home)

            registered = root / "registered"
            registered.mkdir()
            (registered / "README.md").write_text(
                task_readme("registered-id", "registered-task"),
                encoding="utf-8",
            )
            unregistered = root / "unregistered"
            unregistered.mkdir()
            (unregistered / "README.md").write_text(
                task_readme("unregistered-id", "unregistered-task"),
                encoding="utf-8",
            )
            subprocess.run(
                [str(catalog), "register", "--path", str(registered)],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )

            result = subprocess.run(
                [sys.executable, str(RECOVER), "--format", "json"],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 2)
            self.assertFalse(payload["tss_checked"])
            self.assertEqual(
                [task["task"] for task in payload["tasks"]],
                ["registered-task"],
            )
            self.assertEqual(
                Path(payload["tasks"][0]["execution_folder"]),
                registered.resolve(),
            )
            self.assertEqual(payload["tasks"][0]["tss_target"], "local:registered-task")


if __name__ == "__main__":
    unittest.main()
