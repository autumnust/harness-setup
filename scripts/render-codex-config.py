#!/usr/bin/env python3
"""Render Codex root-agent settings while preserving unrelated TOML text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 hosts still get the narrow text checks.
    tomllib = None


TABLE_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
ARRAY_TABLE_RE = re.compile(r"^\s*\[\[([^\[\]]+)\]\]\s*(?:#.*)?$")
MAX_DEPTH_RE = re.compile(r"^(\s*)max_depth\s*=.*$")
MANAGED_MCP_SERVERS = (
    "linear",
    "linkify",
    "maas_gdrive",
    "maas_jira",
    "maas_slack",
)


def table_header(line: str) -> tuple[str, bool] | None:
    if match := ARRAY_TABLE_RE.match(line):
        return match.group(1).strip(), True
    if match := TABLE_RE.match(line):
        return match.group(1).strip(), False
    return None


def set_root_string(lines: list[str], key: str, value: str) -> None:
    end = next((i for i, line in enumerate(lines) if table_header(line)), len(lines))
    key_re = re.compile(rf"^(\s*){re.escape(key)}\s*=.*$")
    matches = [i for i in range(end) if key_re.match(lines[i])]
    if len(matches) > 1:
        raise ValueError(f"config contains more than one root {key} key")
    rendered = f"{key} = {json.dumps(value, ensure_ascii=True)}"
    if matches:
        index = matches[0]
        indent = key_re.match(lines[index]).group(1)
        lines[index] = indent + rendered
    else:
        lines.insert(end, rendered)


def set_max_depth(lines: list[str], depth: int) -> None:
    tables = [
        (i, header[0], header[1])
        for i, line in enumerate(lines)
        if (header := table_header(line))
    ]
    agent_headers = [i for i, name, is_array in tables if name == "agents" and not is_array]
    agent_child_headers = [
        i for i, name, is_array in tables if name.startswith("agents.") and not is_array
    ]
    if len(agent_headers) > 1:
        raise ValueError("config contains more than one [agents] table")

    if not agent_headers:
        text = "\n".join(lines)
        if re.search(r"^\s*agents(?:\.[A-Za-z0-9_-]+)?\s*=", text, flags=re.MULTILINE):
            raise ValueError(
                "config uses a dotted or inline agents value; refusing an ambiguous rewrite"
            )
        if agent_child_headers:
            insert_at = min(agent_child_headers)
            lines[insert_at:insert_at] = ["[agents]", f"max_depth = {depth}", ""]
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["[agents]", f"max_depth = {depth}"])
        return

    start = agent_headers[0]
    end = len(lines)
    later_tables = [i for i, _name, _is_array in tables if i > start]
    if later_tables:
        end = min(later_tables)
    matches = [i for i in range(start + 1, end) if MAX_DEPTH_RE.match(lines[i])]
    if len(matches) > 1:
        raise ValueError("[agents] contains more than one max_depth key")
    if matches:
        index = matches[0]
        indent = MAX_DEPTH_RE.match(lines[index]).group(1)
        lines[index] = f"{indent}max_depth = {depth}"
    else:
        lines.insert(end, f"max_depth = {depth}")


def set_existing_mcp_servers_enabled(lines: list[str], enabled: bool) -> None:
    """Set the managed MCP servers' enabled flag, without adding new servers."""
    tables = [
        (i, header[0], header[1])
        for i, line in enumerate(lines)
        if (header := table_header(line))
    ]
    managed_tables = {f"mcp_servers.{server}" for server in MANAGED_MCP_SERVERS}
    enabled_re = re.compile(r"^(\s*)enabled\s*=.*$")

    # Work backward so inserting a key does not invalidate the remaining indices.
    for index in range(len(tables) - 1, -1, -1):
        start, name, is_array = tables[index]
        if is_array or name not in managed_tables:
            continue
        end = tables[index + 1][0] if index + 1 < len(tables) else len(lines)
        matches = [i for i in range(start + 1, end) if enabled_re.match(lines[i])]
        if len(matches) > 1:
            raise ValueError(f"[{name}] contains more than one enabled key")
        if matches:
            indent = enabled_re.match(lines[matches[0]]).group(1)
            lines[matches[0]] = f"{indent}enabled = {str(enabled).lower()}"
        else:
            lines.insert(start + 1, f"enabled = {str(enabled).lower()}")


def render(
    text: str,
    depth: int,
    model: str,
    reasoning_effort: str,
    managed_mcp_enabled: bool = False,
) -> str:
    lines = text.splitlines()
    set_root_string(lines, "model", model)
    set_root_string(lines, "model_reasoning_effort", reasoning_effort)
    set_max_depth(lines, depth)
    set_existing_mcp_servers_enabled(lines, managed_mcp_enabled)

    result = "\n".join(lines).rstrip() + "\n"
    if tomllib is not None:
        try:
            parsed = tomllib.loads(result)
        except Exception as exc:
            raise ValueError(f"rendered config is invalid TOML: {exc}") from exc
        if parsed.get("model") != model:
            raise ValueError("rendered config did not set the coordinator model")
        if parsed.get("model_reasoning_effort") != reasoning_effort:
            raise ValueError("rendered config did not set coordinator reasoning effort")
        if parsed.get("agents", {}).get("max_depth") != depth:
            raise ValueError("rendered config did not set agents.max_depth")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument(
        "--enable-managed-mcp",
        action="store_true",
        help="Keep the managed MCP servers enabled for the NVIDIA laptop profile.",
    )
    args = parser.parse_args()
    if args.max_depth < 1:
        parser.error("--max-depth must be positive")
    try:
        text = args.input.read_text(encoding="utf-8") if args.input and args.input.exists() else ""
        args.output.write_text(
            render(
                text,
                args.max_depth,
                args.model,
                args.reasoning_effort,
                managed_mcp_enabled=args.enable_managed_mcp,
            ),
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
