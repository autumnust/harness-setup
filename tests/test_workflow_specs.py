from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import tomllib
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
        self.assertEqual(adapters["codex"]["models"]["executor"], "gpt-5.6-sol")
        self.assertEqual(
            self.role(manifest, "executor")["reasoning_policy"], "high"
        )
        self.assertEqual(
            adapters["codex"]["review_bridge"],
            {
                "backend": "claude-code",
                "caller": "codex",
                "model": "opus",
                "effort": "max",
            },
        )
        self.assertEqual(
            adapters["claude"]["review_bridge"],
            {
                "backend": "codex-plugin-native-review",
                "caller": "claude",
                "model": "gpt-5.6-sol",
                "effort": "provider-default",
            },
        )
        claude_settings = json.loads((REPO_ROOT / "claude/settings.json").read_text())
        self.assertEqual(claude_settings["model"], adapters["claude"]["models"]["fast"])
        self.assertEqual(
            claude_settings["effortLevel"], adapters["claude"]["effort"]["medium"]
        )
        self.assertEqual(
            set(manifest["workflows"]),
            {"default", "education-mode", "pr-maintenance", "pr-review"},
        )
        interfaces = {
            role["name"]: role["human_interface"] for role in manifest["roles"]
        }
        self.assertEqual(interfaces["coordinator"], "default")
        self.assertEqual(
            self.role(manifest, "coordinator")["model_policy"], "fast"
        )
        self.assertNotIn("educator", interfaces)
        self.assertTrue(
            all(
                policy == "none"
                for name, policy in interfaces.items()
                if name != "coordinator"
            )
        )

    def test_rejects_child_spawning(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "executor")["allowed_children"] = ["reviewer"]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(render_agents.SpecError, "must be a leaf"):
            render_agents.validate(self.source)

    def test_reviewer_is_only_cross_provider_review_invoker(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "executor")["required_skills"] = [
            "cross-provider-review"
        ]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError,
            "sole cross-provider review invoker",
        ):
            render_agents.validate(self.source)

    def test_requires_education_mode_workflow(self) -> None:
        manifest = self.manifest()
        del manifest["workflows"]["education-mode"]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(render_agents.SpecError, "complete workflow set"):
            render_agents.validate(self.source)

    def test_education_mode_is_owned_by_coordinator(self) -> None:
        workflow = (self.source / "workflows/education.md").read_text()
        self.assertIn("not a separate agent", workflow)
        self.assertIn("A single ordinary question stays in the current", workflow)
        self.assertIn("coordinator teaches the human user directly", workflow)
        self.assertIn("existing fast model policy", workflow)
        self.assertIn("existing child or spawn a new child", workflow)
        self.assertIn("By default, create no execution folder", workflow)
        self.assertIn("Outside education mode, do not load learner profiles", workflow)
        self.assertIn("A missing policy means `ask`", workflow)

    def test_rejects_broad_pr_maintainer_messaging(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "pr-maintainer")["allowed_message_targets"].append(
            "reviewer"
        )
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError, "pr-maintainer may message only"
        ):
            render_agents.validate(self.source)

    def test_rejects_direct_human_interaction_for_operational_child(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "executor")["human_interface"] = "default"
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError, "direct human interaction is not permitted"
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

        del config["learner_profile_update_policy"]
        render_agents.validate_runtime_config_document(config, "legacy test")

        config["learner_profile_update_policy"] = "sometimes"
        with self.assertRaisesRegex(render_agents.SpecError, "must be ask, auto, or off"):
            render_agents.validate_runtime_config_document(config, "test")
        config["learner_profile_update_policy"] = "ask"

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
            output / "codex/agent-harness-pr-maintainer.toml"
        ).read_text()
        self.assertIn("Permitted child roles from this role: none", pr_maintainer)
        self.assertIn(
            "Permitted direct message targets: coordinator, executor", pr_maintainer
        )
        self.assertFalse((output / "codex/agent-harness-educator.toml").exists())
        self.assertFalse((output / "claude/educator.md").exists())

        reviewer = (output / "codex/agent-harness-reviewer.toml").read_text()
        self.assertIn('model = "gpt-5.6-luna"', reviewer)
        self.assertIn('model_reasoning_effort = "low"', reviewer)
        self.assertIn("External backend: claude-code", reviewer)
        self.assertIn("External model: opus", reviewer)
        self.assertIn("External effort: max", reviewer)
        self.assertIn("--caller codex", reviewer)

        claude_reviewer = (output / "claude/reviewer.md").read_text()
        self.assertIn("  - cross-provider-review", claude_reviewer)
        self.assertIn("External backend: codex-plugin-native-review", claude_reviewer)
        self.assertIn("External model: gpt-5.6-sol", claude_reviewer)
        self.assertIn("--caller claude", claude_reviewer)


if __name__ == "__main__":
    unittest.main()
