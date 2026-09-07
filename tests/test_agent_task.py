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
        return {"schema_version": 1, "records": []}
    return json.loads(state_path.read_text(encoding="utf-8"))

def metadata(path):
    lines = (path / "README.md").read_text(encoding="utf-8").splitlines()
    values = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
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
        "runtime_host": values.get("runtime_host", ""),
        "tmux_session": values.get("tmux_session", ""),
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
    print(json.dumps({"schema_version": 1, "record": record}))
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
    print(json.dumps({"schema_version": 1, "registered": len(state["records"])}))
else:
    print("unsupported", file=sys.stderr)
    raise SystemExit(4)
'''


SESSION_PROGRAM = '''#!/usr/bin/env python3
import json
import sys
task_dir = sys.argv[sys.argv.index("--task-dir") + 1]
host = sys.argv[sys.argv.index("--tss-host") + 1]
name = (
    sys.argv[sys.argv.index("--session-name") + 1]
    if "--session-name" in sys.argv
    else "generated-session"
)
print(json.dumps({
    "created": True,
    "session_name": name,
    "task_dir": task_dir,
    "tss_host": host,
    "tss_target": host + ":" + name,
}))
'''


class AgentTaskTests(unittest.TestCase):
    def run_script(
        self,
        script: Path,
        *args: str,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=check,
            text=True,
            capture_output=True,
            env=env,
        )

    def catalog_fixture(self, root: Path) -> tuple[Path, dict[str, str]]:
        catalog = root / "task-catalog"
        catalog.write_text(CATALOG_PROGRAM, encoding="utf-8")
        catalog.chmod(0o755)
        env = os.environ.copy()
        env["TEST_CATALOG_STATE"] = str(root / "catalog.json")
        env["TEST_CATALOG_LOG"] = str(root / "catalog.log")
        return catalog, env

    def catalog_calls(self, root: Path) -> list[list[str]]:
        log = root / "catalog.log"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def test_hydrates_registers_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "Daily Life"
            destination.mkdir()
            catalog, env = self.catalog_fixture(root)
            result = self.run_script(
                HYDRATE,
                "--name", "personal finance",
                "--objective", "Organize accounts and tax records",
                "--destination", str(destination),
                "--catalog-cli", str(catalog),
                "--format", "json",
                env=env,
            )
            task = destination / "personal finance"
            payload = json.loads(result.stdout)
            self.assertEqual(payload["path"], str(task.resolve()))
            self.assertTrue(payload["catalog_registered"])
            self.assertTrue((task / "inbox").is_dir())
            self.assertIn(
                "Organize accounts and tax records",
                (task / "README.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                self.catalog_calls(root),
                [["register", "--path", str(task.resolve()), "--format", "json"]],
            )

            repeated = self.run_script(
                HYDRATE,
                "--name", "personal finance",
                "--destination", str(destination),
                "--catalog-cli", str(catalog),
                check=False,
                env=env,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to overwrite", repeated.stderr)
            self.assertEqual(len(self.catalog_calls(root)), 1)

    def test_discovery_uses_only_the_fixed_catalog_list_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            for name in ("taxes", "travel"):
                self.run_script(
                    HYDRATE,
                    "--name", name,
                    "--objective", f"Handle {name}",
                    "--destination", str(root),
                    "--catalog-cli", str(catalog),
                    env=env,
                )
            state_path = Path(env["TEST_CATALOG_STATE"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            next(record for record in state["records"] if record["title"] == "taxes")[
                "status"
            ] = "blocked"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            unregistered = root / "unregistered"
            unregistered.mkdir()
            (unregistered / "README.md").write_text(
                "---\nagent_task: 1\nid: outside-catalog\ntitle: hidden\n---\n",
                encoding="utf-8",
            )
            result = self.run_script(
                DISCOVER,
                str(root),
                "--catalog-cli", str(catalog),
                "--format", "json",
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["source"], "task-catalog")
            self.assertEqual(
                [task["title"] for task in payload["tasks"]], ["taxes", "travel"]
            )
            self.assertEqual(payload["tasks"][0]["objective"], "Handle taxes")
            self.assertNotIn("hidden", [task["title"] for task in payload["tasks"]])
            self.assertEqual(
                self.catalog_calls(root)[-1],
                ["list", "--format", "json", "--kind", "agent-task"],
            )

    def test_missing_catalog_keeps_created_folder_and_discovery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing = root / "missing-catalog"
            result = self.run_script(
                HYDRATE,
                "--name", "offline",
                "--destination", str(root),
                "--catalog-cli", str(missing),
                "--format", "json",
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue((root / "offline" / "README.md").is_file())
            self.assertFalse(json.loads(result.stdout)["catalog_registered"])
            self.assertIn("catalog registration failed", result.stderr)

            discovery = self.run_script(
                DISCOVER,
                "--catalog-cli", str(missing),
                "--format", "json",
                check=False,
            )
            self.assertNotEqual(discovery.returncode, 0)
            self.assertIn("cannot run task catalog", discovery.stderr)

    def test_public_cli_init_reads_config_and_returns_stable_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            session = root / "session.py"
            session.write_text(SESSION_PROGRAM, encoding="utf-8")
            config = root / "config.json"
            config.write_text(
                json.dumps({"task_runtime": {"tss": {"host_alias": "local"}}}),
                encoding="utf-8",
            )
            result = self.run_script(
                AGENT_TASK,
                "init",
                "--name", "portable-task",
                "--objective", "Exercise the public command",
                "--destination", str(root),
                "--config", str(config),
                "--session-name", "portable",
                "--catalog-cli", str(catalog),
                "--task-session-cli", str(session),
                "--format", "json",
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["catalog_registered"])
            self.assertTrue(payload["session_started"])
            self.assertEqual(payload["tss_target"], "local:portable")
            self.assertTrue(Path(payload["path"]).is_dir())

    def test_public_cli_preserves_folder_when_session_setup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            session = root / "bad-session.py"
            session.write_text(
                "import sys\nprint('session unavailable', file=sys.stderr)\nraise SystemExit(7)\n",
                encoding="utf-8",
            )
            result = self.run_script(
                AGENT_TASK,
                "init",
                "--name", "kept-task",
                "--destination", str(root),
                "--tss-host", "local",
                "--catalog-cli", str(catalog),
                "--task-session-cli", str(session),
                "--format", "json",
                check=False,
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 3)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["catalog_registered"])
            self.assertFalse(payload["session_started"])
            self.assertTrue((root / "kept-task" / "README.md").is_file())
            self.assertIn("session unavailable", payload["error"])

    def test_public_cli_reconcile_is_explicit_then_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, env = self.catalog_fixture(root)
            task = root / "older-task"
            task.mkdir()
            (task / "README.md").write_text(
                "---\nagent_task: 1\nid: old-id\ntitle: older\nstatus: active\n---\n",
                encoding="utf-8",
            )
            result = self.run_script(
                AGENT_TASK,
                "reconcile",
                str(root),
                "--catalog-cli", str(catalog),
                "--format", "json",
                env=env,
            )
            self.assertEqual(json.loads(result.stdout)["tasks"][0]["title"], "older")
            self.assertEqual(
                [call[0] for call in self.catalog_calls(root)],
                ["reconcile", "list"],
            )


if __name__ == "__main__":
    unittest.main()
