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
        self.assertEqual(adapters["claude"]["models"]["coordinator"], "sonnet")
        self.assertEqual(
            adapters["codex"]["models"]["coordinator"], "gpt-5.6-terra"
        )
        self.assertEqual(adapters["codex"]["models"]["executor"], "gpt-5.6-sol")
        self.assertEqual(
            self.role(manifest, "executor")["reasoning_policy"], "high"
        )
        self.assertEqual(
            self.role(manifest, "reviewer")["model_policy"], "capable"
        )
        self.assertEqual(
            self.role(manifest, "reviewer")["reasoning_policy"], "medium"
        )
        self.assertEqual(
            self.role(manifest, "reviewer")["required_workflows"], ["pr-review"]
        )
        self.assertEqual(
            self.role(manifest, "coordinator")["required_workflows"],
            ["pr-maintenance", "pr-review"],
        )
        self.assertEqual(
            self.role(manifest, "pr-maintainer")["required_workflows"],
            ["pr-maintenance"],
        )
        self.assertEqual(adapters["codex"]["reasoning_effort"]["highest"], "max")
        self.assertEqual(adapters["claude"]["effort"]["highest"], "max")
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
        self.assertEqual(
            claude_settings["model"], adapters["claude"]["models"]["coordinator"]
        )
        self.assertEqual(
            claude_settings["effortLevel"], adapters["claude"]["effort"]["medium"]
        )
        self.assertEqual(
            set(manifest["workflows"]),
            {"pr-maintenance", "pr-review"},
        )
        interfaces = {
            role["name"]: role["human_interface"] for role in manifest["roles"]
        }
        self.assertEqual(interfaces["coordinator"], "default")
        self.assertEqual(
            self.role(manifest, "coordinator")["model_policy"], "coordinator"
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

    def test_reviewer_must_include_pr_review_workflow(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "reviewer")["required_workflows"] = []
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError,
            "required_workflows must be",
        ):
            render_agents.validate(self.source)

    def test_roles_must_declare_exact_workflow_dependencies(self) -> None:
        manifest = self.manifest()
        self.role(manifest, "pr-maintainer")["required_workflows"] = []
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError,
            "pr-maintainer: required_workflows must be",
        ):
            render_agents.validate(self.source)

        manifest = self.manifest()
        self.role(manifest, "pr-maintainer")["required_workflows"] = [
            "pr-maintenance"
        ]
        self.role(manifest, "coordinator")["required_workflows"] = [
            "pr-maintenance"
        ]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(
            render_agents.SpecError,
            "coordinator: required_workflows must be",
        ):
            render_agents.validate(self.source)

    def test_reviewer_result_categories_have_one_authoritative_definition(
        self,
    ) -> None:
        workflow = (self.source / "workflows/pr-review.md").read_text()
        self.assertEqual(workflow.count("**Finding:**"), 1)
        self.assertNotIn("**Suggested action item:**", workflow)
        self.assertNotIn("**Disagreement:**", workflow)
        for relative in (
            "roles/reviewer.md",
            "contracts/review-independence.md",
            "contracts/result.md",
        ):
            text = (self.source / relative).read_text()
            self.assertNotIn("**Finding:**", text)
            self.assertNotIn("**Suggested action item:**", text)
            self.assertNotIn("**Disagreement:**", text)

    def test_requires_complete_shared_workflow_set(self) -> None:
        manifest = self.manifest()
        del manifest["workflows"]["pr-review"]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(render_agents.SpecError, "complete workflow set"):
            render_agents.validate(self.source)

    def test_education_is_owned_by_coordinator(self) -> None:
        coordinator = (self.source / "roles/coordinator.md").read_text()
        normalized = " ".join(coordinator.split())
        for marker in (
            "not a separate agent",
            "A single ordinary question remains in the current procedure",
            "Teach the human user directly",
            "existing model policy",
            "resume or create a bounded child",
            "That child uses `mode: fast`",
            "By default, create no execution folder",
            "Do not load a profile outside education",
            "A missing policy means `ask`",
        ):
            self.assertIn(marker, normalized)

    def test_pr_requests_escalate_to_full_work(self) -> None:
        coordinator = (self.source / "roles/coordinator.md").read_text()
        handoff = (self.source / "contracts/handoff.md").read_text()
        maintenance = (self.source / "workflows/pr-maintenance.md").read_text()
        self.assertIn("creates or monitors a PR", coordinator)
        self.assertIn("A requested PR is full work.", handoff)
        self.assertIn("Full-mode only.", maintenance)

    def test_coordinator_owns_human_readable_html_contract(self) -> None:
        manifest, _adapters = render_agents.validate(self.source)
        coordinator = self.role(manifest, "coordinator")
        self.assertIn(
            "contracts/human-readable-html.md", coordinator["contracts"]
        )

        contract = (
            self.source / "contracts/human-readable-html.md"
        ).read_text()
        for requirement in (
            "self-contained",
            "responsive",
            "status color with text",
            "desktop width and one narrow width",
        ):
            self.assertIn(requirement, contract)

        template = (
            self.source / "templates/education-brief.html"
        ).read_text()
        for marker in (
            '<meta name="viewport"',
            "font-size: 16px",
            "line-height: 1.6",
            "@media (max-width: 560px)",
            "@media print",
            'class="skip-link"',
            "overflow-x: auto",
        ):
            self.assertIn(marker, template)

    def test_procedures_have_one_authoritative_source(
        self,
    ) -> None:
        global_docs = "\n".join(
            path.read_text()
            for path in (
                REPO_ROOT / "README.md",
                REPO_ROOT / "home/AGENTS.md",
            )
        )
        coordinator = (self.source / "roles/coordinator.md").read_text()
        coordinator_normalized = " ".join(coordinator.split())
        self.assertEqual(coordinator.count("Present its readiness result"), 1)
        self.assertIn("**Fast**", coordinator)
        self.assertIn("**Full**", coordinator)
        self.assertNotIn("Present its readiness result", global_docs)

        education_other = "\n".join(
            (self.source / relative).read_text()
            for relative in (
                "contracts/education-routing.md",
                "contracts/learning-state.md",
            )
        )
        for marker in (
            "A single ordinary question remains",
            "By default, create no execution folder",
            "A product implementation request exits",
        ):
            self.assertEqual(coordinator_normalized.count(marker), 1)
            self.assertNotIn(marker, education_other)
            self.assertNotIn(marker, global_docs)

        maintenance = (self.source / "workflows/pr-maintenance.md").read_text()
        maintenance_other = "\n".join(
            (self.source / relative).read_text()
            for relative in (
                "roles/pr-maintainer.md",
                "contracts/pr-queue.md",
            )
        )
        for marker in (
            "**Registered Executor route:**",
            "**Coordinator route:**",
            "defaulting to ten minutes",
        ):
            self.assertEqual(maintenance.count(marker), 1)
            self.assertNotIn(marker, maintenance_other)
            self.assertNotIn(marker, global_docs)

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
        self.assertEqual(pr_maintainer.count("# PR maintenance workflow"), 1)
        self.assertEqual(
            pr_maintainer.count("**Registered Executor route:**"),
            1,
        )
        self.assertEqual(pr_maintainer.count("**Coordinator route:**"), 1)
        self.assertFalse((output / "codex/agent-harness-educator.toml").exists())
        self.assertFalse((output / "claude/educator.md").exists())

        reviewer = (output / "codex/agent-harness-reviewer.toml").read_text()
        self.assertIn('model = "gpt-5.6-terra"', reviewer)
        self.assertIn('model_reasoning_effort = "medium"', reviewer)
        self.assertIn("External backend: claude-code", reviewer)
        self.assertIn("External model: opus", reviewer)
        self.assertIn("External effort: max", reviewer)
        self.assertIn("--caller codex", reviewer)
        self.assertIn("# PR review workflow", reviewer)
        self.assertIn("waits for its opinion", reviewer)
        self.assertEqual(reviewer.count("**Finding:**"), 1)
        self.assertNotIn("**Suggested action item:**", reviewer)
        self.assertNotIn("**Disagreement:**", reviewer)

        claude_reviewer = (output / "claude/reviewer.md").read_text()
        self.assertIn("model: sonnet", claude_reviewer)
        self.assertIn("effort: medium", claude_reviewer)
        self.assertIn("  - cross-provider-review", claude_reviewer)
        self.assertIn("External backend: codex-plugin-native-review", claude_reviewer)
        self.assertIn("External model: gpt-5.6-sol", claude_reviewer)
        self.assertIn("--caller claude", claude_reviewer)
        self.assertIn("# PR review workflow", claude_reviewer)


if __name__ == "__main__":
    unittest.main()
