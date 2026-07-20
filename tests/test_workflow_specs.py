from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/render-agents.py"
SPEC = importlib.util.spec_from_file_location("render_agents", MODULE_PATH)
assert SPEC and SPEC.loader
render_agents = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_agents)


class WorkflowSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "agent-workflows"
        shutil.copytree(REPO_ROOT / "agent-workflows", self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest(self) -> dict:
        return json.loads((self.source / "manifest.json").read_text())

    def write_manifest(self, manifest: dict) -> None:
        (self.source / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def role(self, manifest: dict, name: str) -> dict:
        return next(role for role in manifest["roles"] if role["name"] == name)

    def test_current_policy_and_provider_models(self) -> None:
        manifest, adapters = render_agents.validate(self.source)
        children = [role for role in manifest["roles"] if role["kind"] == "subagent"]
        self.assertTrue(all(role["allowed_children"] == [] for role in children))
        self.assertEqual(manifest["max_depth"], 2)
        self.assertEqual(adapters["claude"]["models"]["deep"], "opus")
        self.assertEqual(adapters["codex"]["models"]["deep"], "gpt-5.6-sol")

    def test_rejects_child_spawning(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "executor")["allowed_children"] = ["educator"]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(render_agents.SpecError, "must be a leaf"):
            render_agents.validate(self.source)

    def test_rejects_broad_pr_maintainer_messaging(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "pr-maintainer")["allowed_message_targets"].append(
            "educator"
        )
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError, "pr-maintainer may message only"
        ):
            render_agents.validate(self.source)

    def test_rejects_weaker_review_independence(self) -> None:
        defaults_path = self.source / "runtime-config.defaults.json"
        defaults = json.loads(defaults_path.read_text())
        defaults["review_independence"] = "different-model"
        defaults_path.write_text(json.dumps(defaults, indent=2) + "\n")
        with self.assertRaisesRegex(
            render_agents.SpecError, "different-foundation review"
        ):
            render_agents.validate(self.source)

    def test_validates_configured_runtime_backends(self) -> None:
        config = json.loads(
            (self.source / "runtime-config.defaults.json").read_text()
        )
        config["configured"] = True
        config["review_backends"] = [
            {"id": "claude", "foundation": "anthropic"},
            {"id": "codex", "foundation": "openai"},
        ]
        render_agents.validate_runtime_config_document(config, "test")

        config["review_backends"][1]["foundation"] = ""
        with self.assertRaisesRegex(render_agents.SpecError, "non-empty string"):
            render_agents.validate_runtime_config_document(config, "test")

        config["review_backends"][1] = {
            "id": "claude",
            "foundation": "openai",
        }
        with self.assertRaisesRegex(render_agents.SpecError, "ids must be unique"):
            render_agents.validate_runtime_config_document(config, "test")

    def test_rendered_children_are_leaves_with_message_limits(self) -> None:
        manifest, adapters = render_agents.validate(self.source)
        output = Path(self.temp.name) / "rendered"
        render_agents.render(self.source, output, manifest, adapters)

        for path in (output / "claude").glob("*.md"):
            frontmatter = path.read_text().split("---", 2)[1]
            disallowed = next(
                line for line in frontmatter.splitlines() if line.startswith("disallowedTools:")
            )
            self.assertIn("Agent", disallowed)
        pr_maintainer = (
            output / "codex/lei-harness-pr-maintainer.toml"
        ).read_text()
        self.assertIn("Permitted child roles from this role: none", pr_maintainer)
        self.assertIn(
            "Permitted direct message targets: coordinator, executor", pr_maintainer
        )


if __name__ == "__main__":
    unittest.main()
