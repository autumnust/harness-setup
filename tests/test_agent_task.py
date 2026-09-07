from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "agent-skills" / "agent-task"
HYDRATE = SKILL_ROOT / "scripts" / "hydrate_task.py"
DISCOVER = SKILL_ROOT / "scripts" / "discover_tasks.py"
AGENT_TASK = REPO_ROOT / "scripts" / "agent-task.py"


CATALOG_PROGRAM = '''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["TEST_CATALOG_STATE"])
log_path = Path(os.environ["TEST_CATALOG_LOG"])
with log_path.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")

def load():
    if not state_path.is_file():
        return {"schema_version": 2, "records": []}
    return json.loads(state_path.read_text(encoding="utf-8"))

def metadata(path):
    lines = (path / "README.md").read_text(encoding="utf-8").splitlines()
    values = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip("'")
    body = "\\n".join(lines)
    def section(title):
        marker = "## " + title
        after = body.split(marker, 1)
        if len(after) != 2:
            return ""
        return after[1].split("## ", 1)[0].strip().replace("\\n", " ")
    return {
        "record_type": "task",
        "kind": "agent-task",
        "id": values["id"],
        "title": values.get("title", path.name),
        "status": values.get("status", "unknown"),
        "created": values.get("created", ""),
        "updated": values.get("updated", ""),
        "objective": section("Current objective"),
        "current_state": section("Current state"),
        "next_task": section("Immediate next task"),
        "path": str(path.resolve()),
        "present": True,
    }

command = sys.argv[1]
if command == "register":
    task_path = Path(sys.argv[sys.argv.index("--path") + 1])
    state = load()
    record = metadata(task_path)
    state["records"] = [
        item for item in state["records"] if item["id"] != record["id"]
    ] + [record]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    print(json.dumps({"schema_version": 2, "records": [record]}))
elif command == "list":
    print(json.dumps(load()))
elif command == "reconcile":
    state = load()
    for raw_root in sys.argv[2:sys.argv.index("--format")]:
        for readme in Path(raw_root).rglob("README.md"):
            text = readme.read_text(encoding="utf-8")
            if "agent_task: 1" not in text:
                continue
            record = metadata(readme.parent)
            state["records"] = [
                item for item in state["records"] if item["id"] != record["id"]
            ] + [record]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    print(json.dumps({"schema_version": 2, "registered": len(state["records"])}))
else:
    print("unsupported", file=sys.stderr)
    raise SystemExit(4)
'''


class AgentTaskTests(unittest.TestCase):
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
        if check and result.returncode:
            self.fail(f"{script.name} failed: {result.stderr}")
        return result

    def catalog_fixture(self, root: Path) -> tuple[Path, dict[str, str]]:
        catalog = root / "task-catalog"
        catalog.write_text(CATALOG_PROGRAM, encoding="utf-8")
        catalog.chmod(0o755)
        env = os.environ.copy()
        env["TEST_CATALOG_STATE"] = str(root / "catalog.json")
        env["TEST_CATALOG_LOG"] = str(root / "catalog.log")
        return catalog, env

    def catalog_calls(self, root: Path) -> list[list[str]]:
        return [
            json.loads(line)
            for line in (root / "catalog.log").read_text(encoding="utf-8").splitlines()
        ]

    def test_hydrates_registers_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "Daily Life"
            destination.mkdir()
            catalog, env = self.catalog_fixture(root)
            result = self.run_script(
                HYDRATE, "--name", "personal finance", "--objective",
                "Organize accounts and tax records", "--destination", str(destination),
                "--catalog-cli", str(catalog), "--format", "json", env=env,
            )
            task = destination / "personal finance"
            payload = json.loads(result.stdout)
            self.assertEqual(payload["path"], str(task.resolve()))
            self.assertTrue(payload["catalog_registered"])
            self.assertTrue((task / "inbox").is_dir())
            self.assertIn("Organize accounts", (task / "README.md").read_text())

            repeated = self.run_script(
                HYDRATE, "--name", "personal finance", "--destination",
                str(destination), "--catalog-cli", str(catalog), check=False, env=env,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to overwrite", repeated.stderr)

    def test_discovery_uses_only_fixed_catalog_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            for name in ("taxes", "travel"):
                self.run_script(
                    HYDRATE, "--name", name, "--objective", f"Handle {name}",
                    "--destination", str(root), "--catalog-cli", str(catalog), env=env,
                )
            state_path = Path(env["TEST_CATALOG_STATE"])
            state = json.loads(state_path.read_text())
            next(item for item in state["records"] if item["title"] == "taxes")["status"] = "blocked"
            state_path.write_text(json.dumps(state))

            payload = json.loads(
                self.run_script(
                    DISCOVER, str(root), "--catalog-cli", str(catalog),
                    "--format", "json", env=env,
                ).stdout
            )
            self.assertEqual([item["title"] for item in payload["tasks"]], ["taxes", "travel"])
            self.assertNotIn("tss_target", payload["tasks"][0])
            self.assertEqual(
                self.catalog_calls(root)[-1],
                ["list", "--format", "json", "--kind", "agent-task"],
            )
            human = self.run_script(
                AGENT_TASK, "list", str(root), "--catalog-cli", str(catalog),
                "-H", env=env,
            ).stdout
            self.assertIn("General tasks: 2", human)
            self.assertNotIn("session tss", human)

    def test_init_creates_context_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            payload = json.loads(
                self.run_script(
                    AGENT_TASK, "init", "--name", "portable-task", "--objective",
                    "Exercise the public command", "--destination", str(root),
                    "--catalog-cli", str(catalog), "--format", "json", env=env,
                ).stdout
            )
            self.assertEqual(payload["schema_version"], 2)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["catalog_registered"])
            self.assertNotIn("session_started", payload)
            self.assertNotIn("tss_target", payload)

    def test_init_rejects_retired_runtime_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = self.run_script(
                AGENT_TASK, "init", "--name", "not-created", "--destination",
                str(root), "--tss-host", "local", check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unrecognized arguments", result.stderr)
            self.assertFalse((root / "not-created").exists())

    def test_set_state_updates_file_and_catalog_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            self.run_script(
                AGENT_TASK, "init", "--name", "stateful", "--destination", str(root),
                "--catalog-cli", str(catalog), env=env,
            )
            task = root / "stateful"
            readme = task / "README.md"
            readme.write_text(
                readme.read_text().replace(
                    "updated:", "runtime_host: old-host\ntmux_session: old-session\nupdated:", 1
                )
            )
            payload = json.loads(
                self.run_script(
                    AGENT_TASK, "set-state", "--task-dir", str(task),
                    "--status", "waiting", "--summary", "Waiting for input.",
                    "--next-step", "Resume when input arrives.", "--catalog-cli",
                    str(catalog), "--format", "json", env=env,
                ).stdout
            )
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["catalog_registered"])
            updated = readme.read_text()
            self.assertIn("status: 'waiting'", updated)
            self.assertIn("Waiting for input.", updated)
            self.assertIn("Resume when input arrives.", updated)
            self.assertNotIn("runtime_host:", updated)
            self.assertNotIn("tmux_session:", updated)

            missing = root / "missing-catalog"
            completed = json.loads(
                self.run_script(
                    AGENT_TASK, "set-state", "--task-dir", str(task),
                    "--status", "done", "--summary", "Complete.",
                    "--catalog-cli", str(missing), "--format", "json", env=env,
                ).stdout
            )
            self.assertTrue(completed["ok"])
            self.assertFalse(completed["catalog_registered"])
            self.assertIn("status: 'done'", readme.read_text())

    def test_set_state_requires_next_step_for_nonterminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            self.run_script(
                AGENT_TASK, "init", "--name", "stateful", "--destination", str(root),
                "--catalog-cli", str(catalog), env=env,
            )
            result = self.run_script(
                AGENT_TASK, "set-state", "--task-dir", str(root / "stateful"),
                "--status", "paused", "--summary", "Paused.", "--catalog-cli",
                str(catalog), "--format", "json", check=False, env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --next-step", json.loads(result.stdout)["error"])

    def test_reconcile_is_explicit_then_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            task = root / "older-task"
            task.mkdir()
            (task / "README.md").write_text(
                "---\nagent_task: 1\nid: old-id\ntitle: older\nstatus: active\n---\n"
            )
            payload = json.loads(
                self.run_script(
                    AGENT_TASK, "reconcile", str(root), "--catalog-cli", str(catalog),
                    "--format", "json", env=env,
                ).stdout
            )
            self.assertEqual(payload["tasks"][0]["title"], "older")
            self.assertEqual([call[0] for call in self.catalog_calls(root)], ["reconcile", "list"])


if __name__ == "__main__":
    unittest.main()
