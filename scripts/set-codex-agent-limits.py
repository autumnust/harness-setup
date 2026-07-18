#!/usr/bin/env python3
"""Render a Codex config with agents.max_depth set, preserving other text."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 hosts still get the narrow text checks.
    tomllib = None


TABLE_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")
ARRAY_TABLE_RE = re.compile(r"^\s*\[\[([^\[\]]+)\]\]\s*(?:#.*)?$")
KEY_RE = re.compile(r"^(\s*)max_depth\s*=.*$")


def table_header(line: str) -> tuple[str, bool] | None:
    if match := ARRAY_TABLE_RE.match(line):
        return match.group(1).strip(), True
    if match := TABLE_RE.match(line):
        return match.group(1).strip(), False
    return None


def render(text: str, depth: int) -> str:
    lines = text.splitlines()
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
        if re.search(r"^\s*agents(?:\.[A-Za-z0-9_-]+)?\s*=", text, flags=re.MULTILINE):
            raise ValueError("config uses a dotted or inline agents value; refusing an ambiguous rewrite")
        if agent_child_headers:
            insert_at = min(agent_child_headers)
            lines[insert_at:insert_at] = ["[agents]", f"max_depth = {depth}", ""]
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["[agents]", f"max_depth = {depth}"])
    else:
        start = agent_headers[0]
        end = len(lines)
        later_tables = [i for i, _name, _is_array in tables if i > start]
        if later_tables:
            end = min(later_tables)
        matches = [i for i in range(start + 1, end) if KEY_RE.match(lines[i])]
        if len(matches) > 1:
            raise ValueError("[agents] contains more than one max_depth key")
        if matches:
            index = matches[0]
            indent = KEY_RE.match(lines[index]).group(1)
            lines[index] = f"{indent}max_depth = {depth}"
        else:
            lines.insert(end, f"max_depth = {depth}")

    result = "\n".join(lines).rstrip() + "\n"
    if tomllib is not None:
        try:
            parsed = tomllib.loads(result)
        except Exception as exc:
            raise ValueError(f"rendered config is invalid TOML: {exc}") from exc
        if parsed.get("agents", {}).get("max_depth") != depth:
            raise ValueError("rendered config did not set agents.max_depth")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()
    if args.max_depth < 1:
        parser.error("--max-depth must be positive")
    try:
        text = args.input.read_text(encoding="utf-8") if args.input and args.input.exists() else ""
        args.output.write_text(render(text, args.max_depth), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
