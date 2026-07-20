#!/usr/bin/env python3
"""Validate portable agent specs and render Claude/Codex native agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "agent-workflows"


class SpecError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SpecError(f"{path} must contain a JSON object")
    return value


def source_file(source: Path, relative: str) -> Path:
    path = (source / relative).resolve()
    try:
        path.relative_to(source.resolve())
    except ValueError as exc:
        raise SpecError(f"path escapes agent-workflows/: {relative}") from exc
    if not path.is_file():
        raise SpecError(f"missing referenced file: {relative}")
    return path


def validate_runtime_config_document(config: dict[str, Any], label: str) -> None:
    expected = {
        "version",
        "configured",
        "execution_root",
        "learner_state_root",
        "review_backends",
        "supporting_review_backend",
        "external_memory_backend",
        "review_independence",
        "pr_maintenance",
    }
    if set(config) != expected:
        raise SpecError(f"{label}: runtime-config keys differ from the schema")
    if config.get("version") != 1 or not isinstance(config.get("configured"), bool):
        raise SpecError(f"{label}: runtime-config needs version 1 and configured boolean")
    for field in ("execution_root", "learner_state_root"):
        if config[field] is not None and not isinstance(config[field], str):
            raise SpecError(f"{label}: {field} must be a string or null")
    review_backends = config["review_backends"]
    if not isinstance(review_backends, list):
        raise SpecError(f"{label}: review_backends must be a list")
    backend_pairs: list[tuple[str, str]] = []
    for backend in review_backends:
        if not isinstance(backend, dict) or set(backend) != {"id", "foundation"}:
            raise SpecError(f"{label}: each review backend needs only id and foundation")
        backend_id = backend["id"]
        foundation = backend["foundation"]
        if not isinstance(backend_id, str) or not backend_id:
            raise SpecError(f"{label}: review backend id must be a non-empty string")
        if not isinstance(foundation, str) or not foundation:
            raise SpecError(f"{label}: review foundation must be a non-empty string")
        backend_pairs.append((backend_id, foundation))
    backend_ids = [backend_id for backend_id, _foundation in backend_pairs]
    if len(backend_ids) != len(set(backend_ids)):
        raise SpecError(f"{label}: review backend ids must be unique")
    for field in ("supporting_review_backend", "external_memory_backend"):
        if config[field] is not None and not isinstance(config[field], str):
            raise SpecError(f"{label}: {field} must be a string or null")
    if config.get("review_independence") != "different-foundation":
        raise SpecError(f"{label}: runtime-config must require different-foundation review")
    maintenance = config.get("pr_maintenance")
    if not isinstance(maintenance, dict) or set(maintenance) != {
        "poll_interval_seconds"
    }:
        raise SpecError(f"{label}: pr_maintenance has an invalid shape")
    interval = maintenance["poll_interval_seconds"]
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 60:
        raise SpecError(f"{label}: PR polling interval must be at least 60 seconds")


def validate_runtime_config(source: Path) -> None:
    defaults = load_json(source / "runtime-config.defaults.json")
    schema = load_json(source / "runtime-config.schema.json")
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list) or not isinstance(properties, dict):
        raise SpecError("runtime-config schema needs required and properties")
    if set(defaults) != set(required) or set(defaults) != set(properties):
        raise SpecError("runtime-config defaults, required keys, and properties differ")
    validate_runtime_config_document(defaults, "runtime-config defaults")
    if defaults["configured"] is not False:
        raise SpecError("runtime-config defaults must start unconfigured")


def validate(source: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(source / "manifest.json")
    if manifest.get("version") != 1:
        raise SpecError("manifest version must be 1")
    max_depth = manifest.get("max_depth")
    if max_depth != 2:
        raise SpecError("max_depth must remain the defensive provider ceiling of 2")
    workflows = manifest.get("workflows")
    required_workflows = {
        "default",
        "education-only",
        "pr-maintenance",
        "pr-review",
    }
    if not isinstance(workflows, dict) or set(workflows) != required_workflows:
        raise SpecError("manifest must declare the complete workflow set")
    for workflow, relative_path in workflows.items():
        if not isinstance(relative_path, str):
            raise SpecError(f"{workflow}: workflow path must be a string")
        source_file(source, relative_path)
    validate_runtime_config(source)

    roles_value = manifest.get("roles")
    if not isinstance(roles_value, list) or not roles_value:
        raise SpecError("manifest roles must be a non-empty list")

    roles: dict[str, dict[str, Any]] = {}
    display_names: set[str] = set()
    for role in roles_value:
        if not isinstance(role, dict):
            raise SpecError("every role must be an object")
        name = role.get("name")
        if not isinstance(name, str) or not name:
            raise SpecError("every role needs a non-empty name")
        if name in roles:
            raise SpecError(f"duplicate role name: {name}")
        display_name = role.get("display_name")
        if not isinstance(display_name, str) or not display_name:
            raise SpecError(f"{name}: display_name must be a non-empty string")
        if display_name in display_names:
            raise SpecError(f"duplicate role display_name: {display_name}")
        display_names.add(display_name)
        if role.get("human_interface") not in {
            "default",
            "none",
            "registered-session",
        }:
            raise SpecError(f"{name}: invalid human_interface policy")
        if role.get("kind") not in {"root", "subagent"}:
            raise SpecError(f"{name}: kind must be root or subagent")
        if not isinstance(role.get("description"), str):
            raise SpecError(f"{name}: description must be a string")
        if not isinstance(role.get("prompt"), str):
            raise SpecError(f"{name}: prompt must be a path string")
        source_file(source, role["prompt"])
        contracts = role.get("contracts", [])
        if not isinstance(contracts, list) or any(not isinstance(c, str) for c in contracts):
            raise SpecError(f"{name}: contracts must be a string list")
        for contract in contracts:
            source_file(source, contract)
        skills = role.get("required_skills", [])
        if not isinstance(skills, list) or any(not isinstance(s, str) for s in skills):
            raise SpecError(f"{name}: required_skills must be a string list")
        for skill in skills:
            if not (REPO_ROOT / "agent-skills" / skill / "SKILL.md").is_file():
                raise SpecError(f"{name}: missing required skill {skill!r}")
        roles[name] = role

    roots = [name for name, role in roles.items() if role["kind"] == "root"]
    if roots != ["coordinator"]:
        raise SpecError("coordinator must be the only root role")
    if roles["coordinator"]["human_interface"] != "default":
        raise SpecError("coordinator must remain the default human interface")
    if roles["educator"]["human_interface"] != "registered-session":
        raise SpecError("educator must use the registered-session human interface")
    for name, role in roles.items():
        if (
            name not in {"coordinator", "educator"}
            and role["human_interface"] != "none"
        ):
            raise SpecError(f"{name}: direct human interaction is not permitted")

    for name, role in roles.items():
        children = role.get("allowed_children", [])
        if not isinstance(children, list) or any(not isinstance(c, str) for c in children):
            raise SpecError(f"{name}: allowed_children must be a string list")
        if len(children) != len(set(children)):
            raise SpecError(f"{name}: allowed_children contains duplicates")
        unknown = sorted(set(children) - roles.keys())
        if unknown:
            raise SpecError(f"{name}: unknown child roles: {', '.join(unknown)}")
        if any(roles[child]["kind"] == "root" for child in children):
            raise SpecError(f"{name}: a root role cannot be a child")
        if role["kind"] == "subagent" and children:
            raise SpecError(f"{name}: every current subagent must be a leaf")

        targets = role.get("allowed_message_targets", [])
        if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
            raise SpecError(f"{name}: allowed_message_targets must be a string list")
        if len(targets) != len(set(targets)):
            raise SpecError(f"{name}: allowed_message_targets contains duplicates")
        unknown_targets = sorted(set(targets) - roles.keys())
        if unknown_targets:
            raise SpecError(
                f"{name}: unknown message targets: {', '.join(unknown_targets)}"
            )

    subagents = {name for name, role in roles.items() if role["kind"] == "subagent"}
    if set(roles["coordinator"]["allowed_children"]) != subagents:
        raise SpecError("coordinator must be able to spawn every subagent role")
    if set(roles["coordinator"]["allowed_message_targets"]) != subagents:
        raise SpecError("coordinator must be able to message every subagent role")
    for name in subagents - {"pr-maintainer"}:
        if roles[name]["allowed_message_targets"] != ["coordinator"]:
            raise SpecError(f"{name}: may message only the coordinator")
    if set(roles["pr-maintainer"]["allowed_message_targets"]) != {
        "coordinator",
        "executor",
    }:
        raise SpecError("pr-maintainer may message only coordinator and executor")

    def walk(name: str, depth: int, path: tuple[str, ...]) -> None:
        if depth > max_depth:
            raise SpecError(
                f"topology exceeds max_depth={max_depth}: {' -> '.join((*path, name))}"
            )
        if name in path:
            raise SpecError(f"topology cycle: {' -> '.join((*path, name))}")
        for child in roles[name].get("allowed_children", []):
            walk(child, depth + 1, (*path, name))

    walk("coordinator", 0, ())

    adapters: dict[str, dict[str, Any]] = {}
    for provider in ("claude", "codex"):
        adapter = load_json(source / "adapters" / f"{provider}.json")
        models = adapter.get("models", {})
        if not isinstance(models, dict):
            raise SpecError(f"{provider}: models must be an object")
        reasoning_field = "effort" if provider == "claude" else "reasoning_effort"
        reasoning = adapter.get(reasoning_field, {})
        if not isinstance(reasoning, dict):
            raise SpecError(f"{provider}: {reasoning_field} must be an object")
        for role in roles.values():
            policy = role.get("model_policy")
            if policy not in models:
                raise SpecError(f"{provider}: no model mapping for policy {policy!r}")
            reasoning_policy = role.get("reasoning_policy")
            if reasoning_policy not in reasoning:
                raise SpecError(
                    f"{provider}: no {reasoning_field} mapping for policy {reasoning_policy!r}"
                )
        education_session = adapter.get("education_session")
        expected_session_keys = {
            "mode",
            "human_switch_instruction",
            "completion_transport",
            "required_feature",
        }
        if (
            not isinstance(education_session, dict)
            or set(education_session) != expected_session_keys
        ):
            raise SpecError(f"{provider}: invalid education_session adapter")
        for field in ("mode", "human_switch_instruction", "completion_transport"):
            if (
                not isinstance(education_session[field], str)
                or not education_session[field]
            ):
                raise SpecError(
                    f"{provider}: education_session {field} must be non-empty"
                )
        required_feature = education_session["required_feature"]
        if required_feature is not None and not isinstance(required_feature, str):
            raise SpecError(f"{provider}: education_session required_feature is invalid")
        adapters[provider] = adapter

    return manifest, adapters


def role_instructions(
    source: Path,
    manifest: dict[str, Any],
    adapter: dict[str, Any],
    role: dict[str, Any],
) -> str:
    sections = [source_file(source, role["prompt"]).read_text(encoding="utf-8").strip()]
    for contract in role.get("contracts", []):
        sections.append(source_file(source, contract).read_text(encoding="utf-8").strip())
    children = role.get("allowed_children", [])
    child_text = ", ".join(children) if children else "none"
    targets = role.get("allowed_message_targets", [])
    target_text = ", ".join(targets) if targets else "none"
    sections.append(
        "# Installed topology limits\n\n"
        f"The root session starts at depth zero and nesting must not exceed "
        f"depth {manifest['max_depth']}. Permitted child roles from this role: "
        f"{child_text}. Do not spawn any other role. Permitted direct message "
        f"targets: {target_text}. Do not message any other role."
    )
    if role["name"] == "educator":
        session = adapter["education_session"]
        required_feature = session["required_feature"] or "none"
        sections.append(
            "# Provider interactive education adapter\n\n"
            f"Mode: {session['mode']}. Stable display name: {role['display_name']}. "
            f"Human switch instruction: {session['human_switch_instruction']} "
            f"Completion transport: {session['completion_transport']}. "
            f"Required feature: {required_feature}."
        )
    return "\n\n---\n\n".join(sections) + "\n"


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def render_claude(
    source: Path,
    manifest: dict[str, Any],
    adapter: dict[str, Any],
    role: dict[str, Any],
) -> str:
    lines = [
        "---",
        f"name: {role['name']}",
        f"description: {yaml_string(role['description'])}",
        f"model: {adapter['models'][role['model_policy']]}",
        f"effort: {adapter['effort'][role['reasoning_policy']]}",
    ]
    denied_tools: list[str] = []
    if role.get("sandbox_policy") == "read-only":
        lines.append("permissionMode: plan")
        denied_tools.extend(["Write", "Edit"])
    if not role.get("allowed_children"):
        denied_tools.append("Agent")
    if denied_tools:
        lines.append(f"disallowedTools: {', '.join(denied_tools)}")
    skills = role.get("required_skills", [])
    if skills:
        lines.append("skills:")
        lines.extend(f"  - {skill}" for skill in skills)
    lines.extend(["---", "", "<!-- Generated by scripts/render-agents.py; edit agent-workflows/. -->", ""])
    return "\n".join(lines) + role_instructions(source, manifest, adapter, role)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def render_codex(
    source: Path,
    manifest: dict[str, Any],
    adapter: dict[str, Any],
    role: dict[str, Any],
) -> str:
    instructions = role_instructions(source, manifest, adapter, role)
    if '"""' in instructions or "\\" in instructions:
        raise SpecError(f"{role['name']}: prompt contains unsupported TOML multiline text")
    lines = [
        "# Generated by scripts/render-agents.py; edit agent-workflows/.",
        f"name = {toml_string(role['name'])}",
        f"description = {toml_string(role['description'])}",
        f"nickname_candidates = [{toml_string(role['display_name'])}]",
        f"model = {toml_string(adapter['models'][role['model_policy']])}",
        "model_reasoning_effort = "
        + toml_string(adapter["reasoning_effort"][role["reasoning_policy"]]),
    ]
    if role.get("sandbox_policy") == "read-only":
        lines.append('sandbox_mode = "read-only"')
    lines.extend(['developer_instructions = """', instructions.rstrip(), '"""', ""])
    return "\n".join(lines)


def render(source: Path, out: Path, manifest: dict[str, Any], adapters: dict[str, Any]) -> int:
    count = 0
    for provider in ("claude", "codex"):
        (out / provider).mkdir(parents=True, exist_ok=True)
    for role in manifest["roles"]:
        if role["kind"] != "subagent":
            continue
        (out / "claude" / f"{role['name']}.md").write_text(
            render_claude(source, manifest, adapters["claude"], role), encoding="utf-8"
        )
        (out / "codex" / f"lei-harness-{role['name']}.toml").write_text(
            render_codex(source, manifest, adapters["codex"], role), encoding="utf-8"
        )
        count += 1
    return count


def check_rendering(
    source: Path, manifest: dict[str, Any], adapters: dict[str, Any]
) -> None:
    for role in manifest["roles"]:
        if role["kind"] != "subagent":
            continue
        render_claude(source, manifest, adapters["claude"], role)
        render_codex(source, manifest, adapters["codex"], role)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--validate-runtime-config", type=Path)
    args = parser.parse_args(argv)
    if not args.out and not args.check and not args.validate_runtime_config:
        parser.error("provide --out, --check, or --validate-runtime-config")
    try:
        manifest, adapters = validate(args.source)
        if args.out:
            count = render(args.source, args.out, manifest, adapters)
            print(f"rendered {count} subagent roles for Claude and Codex into {args.out}")
        if args.check:
            check_rendering(args.source, manifest, adapters)
            print(
                f"OK: {len(manifest['roles'])} roles, max depth {manifest['max_depth']}, "
                "Claude and Codex adapters valid"
            )
        if args.validate_runtime_config:
            config = load_json(args.validate_runtime_config)
            validate_runtime_config_document(config, str(args.validate_runtime_config))
            print(f"OK: runtime configuration valid: {args.validate_runtime_config}")
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
