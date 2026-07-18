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


def validate(source: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_json(source / "manifest.json")
    if manifest.get("version") != 1:
        raise SpecError("manifest version must be 1")
    max_depth = manifest.get("max_depth")
    if not isinstance(max_depth, int) or max_depth < 1:
        raise SpecError("max_depth must be a positive integer")

    roles_value = manifest.get("roles")
    if not isinstance(roles_value, list) or not roles_value:
        raise SpecError("manifest roles must be a non-empty list")

    roles: dict[str, dict[str, Any]] = {}
    for role in roles_value:
        if not isinstance(role, dict):
            raise SpecError("every role must be an object")
        name = role.get("name")
        if not isinstance(name, str) or not name:
            raise SpecError("every role needs a non-empty name")
        if name in roles:
            raise SpecError(f"duplicate role name: {name}")
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

    for name, role in roles.items():
        children = role.get("allowed_children", [])
        if not isinstance(children, list) or any(not isinstance(c, str) for c in children):
            raise SpecError(f"{name}: allowed_children must be a string list")
        unknown = sorted(set(children) - roles.keys())
        if unknown:
            raise SpecError(f"{name}: unknown child roles: {', '.join(unknown)}")
        if any(roles[child]["kind"] == "root" for child in children):
            raise SpecError(f"{name}: a root role cannot be a child")

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
        adapters[provider] = adapter

    return manifest, adapters


def role_instructions(source: Path, manifest: dict[str, Any], role: dict[str, Any]) -> str:
    sections = [source_file(source, role["prompt"]).read_text(encoding="utf-8").strip()]
    for contract in role.get("contracts", []):
        sections.append(source_file(source, contract).read_text(encoding="utf-8").strip())
    children = role.get("allowed_children", [])
    child_text = ", ".join(children) if children else "none"
    sections.append(
        "# Installed topology limits\n\n"
        f"The root session starts at depth zero and nesting must not exceed "
        f"depth {manifest['max_depth']}. Permitted child roles from this role: "
        f"{child_text}. Do not spawn any other role."
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
    return "\n".join(lines) + role_instructions(source, manifest, role)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def render_codex(
    source: Path,
    manifest: dict[str, Any],
    adapter: dict[str, Any],
    role: dict[str, Any],
) -> str:
    instructions = role_instructions(source, manifest, role)
    if '"""' in instructions or "\\" in instructions:
        raise SpecError(f"{role['name']}: prompt contains unsupported TOML multiline text")
    lines = [
        "# Generated by scripts/render-agents.py; edit agent-workflows/.",
        f"name = {toml_string(role['name'])}",
        f"description = {toml_string(role['description'])}",
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
    args = parser.parse_args(argv)
    try:
        manifest, adapters = validate(args.source)
        if args.out:
            count = render(args.source, args.out, manifest, adapters)
            print(f"rendered {count} subagent roles for Claude and Codex into {args.out}")
        elif not args.check:
            parser.error("provide --out or --check")
        if args.check:
            check_rendering(args.source, manifest, adapters)
            print(
                f"OK: {len(manifest['roles'])} roles, max depth {manifest['max_depth']}, "
                "Claude and Codex adapters valid"
            )
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
