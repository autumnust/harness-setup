#!/usr/bin/env python3
"""Render device-specific Claude settings while preserving host values.

Claude Code also writes this file, for example through /model and /config.
Repository values are defaults only: an existing value always wins. The only
exception is statusLine, which carries this device's node path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MERGED_FIELDS = ("enabledPlugins", "extraKnownMarketplaces", "env")
HARNESS_OWNED_FIELDS = ("statusLine",)
RETIRED_MANAGED_ENV_KEYS = {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"}


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def render(source: Path, existing: Path, node_bin: str) -> dict[str, Any]:
    defaults = json.loads(source.read_text(encoding="utf-8"))
    status_line = defaults.get("statusLine", {})
    command = status_line.get("command", "")
    status_line["command"] = re.sub(
        r'exec\s+"[^"]*/node"', f'exec "{node_bin}"', command
    )
    defaults["statusLine"] = status_line

    current = load_optional(existing)
    config = dict(current)
    for key, value in defaults.items():
        if key in HARNESS_OWNED_FIELDS or key not in config:
            config[key] = value
    for field in MERGED_FIELDS:
        merged = dict(defaults.get(field, {}))
        merged.update(current.get(field, {}))
        if field == "env":
            for key in RETIRED_MANAGED_ENV_KEYS:
                merged.pop(key, None)
        if merged:
            config[field] = merged
        else:
            config.pop(field, None)
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node-bin", required=True)
    parser.add_argument("--existing", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = render(args.source, args.existing, args.node_bin)
        args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
