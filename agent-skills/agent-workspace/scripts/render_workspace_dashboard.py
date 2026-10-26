#!/usr/bin/env python3
"""Render or refresh a workspace task snapshot with an embedded Archify tree."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from catalog_client import list_records
from list_workspace_tasks import STATUS_ORDER, discover, normalize_record
from start_workspace_task import workspace_identity
from dashboard_freshness import (
    atomic_write, check_report, exclude_generated, input_fingerprint,
    metadata_path, refresh_catalog,
)


ASSETS = Path(__file__).resolve().parent.parent / "assets"


def fingerprint(snapshot: dict) -> str:
    script = Path(__file__).resolve()
    return input_fingerprint(snapshot, [
        script, script.with_name("dashboard_freshness.py"), ASSETS / "task-dashboard.html",
        script.parents[3] / "dependencies/external-skills.json",
    ])


def find_archify(explicit: Path | None = None) -> Path:
    harness = Path(os.environ.get("AGENT_HARNESS_HOME", Path.home() / ".agent-harness"))
    candidates = [explicit] if explicit else [
        Path(__file__).resolve().parents[3] / ".resolved-external-skills/archify",
        harness / "current/source/.resolved-external-skills/archify",
        Path.home() / ".agents/skills/archify",
        Path.home() / ".claude/skills/archify",
        Path.home() / ".codex/skills/archify",
    ]
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        script = candidate / "bin/archify.mjs" if candidate.is_dir() else candidate
        if script.is_file():
            return script
    raise ValueError("Archify is unavailable. Install the pinned harness skills or pass --archify <skill-directory>.")


def collect(workspace: Path, statuses: set[str] | None, *, folder_scope: bool = False) -> dict:
    workspace = workspace.expanduser().resolve()
    if folder_scope:
        name = workspace.name + " tasks"
        raw = [r for r in list_records() if r.get("kind") in {"agent-task", "workspace-task"}
               and Path(r["path"]).resolve().is_relative_to(workspace)]
        tasks = [normalize_record(r) for r in raw
                 if statuses is None or r.get("status", "unknown") in statuses]
    else:
        name, _ = workspace_identity(workspace / "workspace.yaml")
        tasks, _ = discover(workspace, statuses)
        raw = list_records("--kind", "workspace-task")
    records = {(r.get("id"), r.get("path")): r for r in raw}
    for task in tasks:
        record = records.get((task["id"], task["path"]), {})
        for key in ("objective", "current_state", "next_task", "last_seen"):
            task[key] = str(record.get(key, ""))
        folder = Path(task["path"])
        task["present"] = folder.is_dir()
        task["links"] = []
        if task["present"]:
            task["links"].append({"label": "Task folder", "url": folder.as_uri()})
            for filename, label in (
                ("README.md", "Task brief"), ("recover.md", "Recovery"),
                ("RECOVERY.md", "Recovery"), ("progress.html", "Progress"),
            ):
                if (folder / filename).is_file():
                    task["links"].append({"label": label, "url": (folder / filename).as_uri()})
    tasks.sort(key=lambda t: (STATUS_ORDER.get(t["status"], 99), t["task_name"].casefold(), t["path"]))
    return {
        "workspace": str(workspace), "workspace_name": name, "folder_scope": folder_scope,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "statuses": sorted(statuses) if statuses else [], "tasks": tasks,
    }


def tree_source(snapshot: dict) -> dict:
    tasks = snapshot["tasks"]
    nodes = [{"id": "workspace", "label": snapshot["workspace_name"],
              "sublabel": f"{len(tasks)} registered task locations"}]
    parents = {}
    for task in tasks:
        parent = str(Path(task["path"]).parent)
        if parent not in parents:
            node_id = f"folder{len(parents)}"
            parents[parent] = node_id
            folder = Path(parent)
            nodes.append({"id": node_id, "parent": "workspace",
                          "label": folder.name, "sublabel": folder.parent.name})
    for index, task in enumerate(tasks):
        nodes.append({"id": f"task{index}", "parent": parents[str(Path(task["path"]).parent)],
                      "label": task["task_name"],
                      "sublabel": task["status"] + (" · folder missing" if not task["present"] else "")})
    return {
        "schema_version": 1, "diagram_type": "tree",
        "meta": {"title": "Workspace task locations", "locale": "en",
                 "output": "map.html", "quality_profile": "showcase"},
        "layout": {"direction": "right"}, "nodes": nodes,
    }


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def linked_text(value: str, folder: Path) -> str:
    """Render plain text and Markdown links without accepting raw HTML."""
    parts, previous = [], 0
    for match in re.finditer(r"\[([^\]\n]+)\]\(([^)\n]+)\)", value):
        parts.append(escape(value[previous:match.start()]))
        label, target = match.groups()
        target = target.strip().removeprefix("<").removesuffix(">")
        try:
            parsed = urlsplit(target)
        except ValueError:
            parts.append(escape(match[0]))
            previous = match.end()
            continue
        if parsed.scheme in {"https", "http"}:
            url = target
        elif not parsed.scheme and not parsed.netloc and target:
            local_path = (folder / unquote(parsed.path or "README.md")).resolve()
            if not local_path.exists():
                parts.append(f'<span title="{escape(local_path)}">{escape(label)} (file unavailable)</span>')
                previous = match.end()
                continue
            url = local_path.as_uri()
            if parsed.fragment:
                url += "#" + parsed.fragment
        else:
            url = ""
        parts.append(f'<a href="{escape(url)}">{escape(label)}</a>' if url else escape(match[0]))
        previous = match.end()
    parts.append(escape(value[previous:]))
    return "".join(parts)


def render(snapshot: dict, diagram: str, refresh_command: str) -> str:
    tasks = snapshot["tasks"]
    counts = Counter(task["status"] for task in tasks)
    rows = []
    for task in tasks:
        links = "".join(f'<a href="{escape(link["url"])}">{escape(link["label"])}</a>'
                        for link in task["links"])
        status = task["status"] if task["status"] in STATUS_ORDER else "unknown"
        details = "".join(
            f'<div><dt>{label}</dt><dd>{linked_text(task[key], Path(task["path"]))}</dd></div>'
            for key, label in (("objective", "Objective"), ("current_state", "Recorded state"), ("next_task", "Next action"))
            if task[key]
        )
        missing = '<p class="missing">Task folder is missing on this machine.</p>' if not task["present"] else ""
        brief = next((link["url"] for link in task["links"] if link["label"] == "Task brief"), "")
        name = escape(task["task_name"])
        if brief:
            name = f'<a href="{escape(brief)}">{name}</a>'
        rows.append(f'''<tr class="task-row" data-status="{status}">
<th scope="row"><div class="task-name">{name}</div>{missing}
<details class="row-details"><summary>Task details</summary><dl>{details}</dl>
<p class="path">{escape(task['path'])}</p>
<p>Catalog observed: {escape(task['last_seen'] or 'not recorded')}<br>
Last used: {escape(task['last_used_at'] or 'not recorded')}</p></details></th>
<td><span class="badge {status}">{escape(task['status'])}</span></td>
<td class="next-action">{linked_text(task['next_task'], Path(task['path'])) or '<span class="muted">Not recorded</span>'}</td>
<td class="updated-date">{escape(task['updated'] or 'Not recorded')}</td>
<td><nav class="row-links" aria-label="Links for {escape(task['task_name'])}">{links}</nav></td></tr>''')
    filters = '<button type="button" data-filter="all" aria-pressed="true">All <span>' + str(len(tasks)) + '</span></button>'
    filters += "".join(
        f'<button type="button" data-filter="{escape(status)}" aria-pressed="false">{escape(status.title())} <span>{count}</span></button>'
        for status, count in counts.items()
    )
    values = {
        "title": escape(snapshot["workspace_name"]),
        "workspace_url": escape(Path(snapshot["workspace"]).as_uri()),
        "generated": escape(snapshot["generated_at"]),
        "max_age_minutes": str(snapshot.get("max_age_minutes", 60)),
        "scope": escape(", ".join(snapshot["statuses"]) if snapshot["statuses"] else "All recorded statuses"),
        "total": str(len(tasks)), "active": str(counts["active"]),
        "attention": str(counts["blocked"] + counts["waiting"]),
        "missing": str(sum(not task["present"] for task in tasks)),
        "filters": filters, "rows": "\n".join(rows),
        "empty_hidden": "hidden" if tasks else "",
        "diagram": escape(diagram), "refresh": escape(refresh_command),
    }
    template = (ASSETS / "task-dashboard.html").read_text(encoding="utf-8")
    # One substitution pass keeps task text containing template markers literal.
    return re.sub(r"@@(\w+)@@", lambda m: values[m[1]], template)


def served_links(document: str, output: Path, web_root: Path) -> str:
    """Map local document links into the selected HTTP document directory."""
    def replace(match: re.Match) -> str:
        prefix, target, suffix, label = match.groups()
        parsed = urlsplit(html.unescape(target))
        path = Path(unquote(parsed.path)).resolve()
        if not path.is_relative_to(web_root):
            return '<span title="Outside the served folder">' + label + ' (outside served folder)</span>'
        relative = quote(os.path.relpath(path, output.parent), safe="/")
        if path.is_dir():
            relative += "/"
        if parsed.fragment:
            relative += "#" + quote(unquote(parsed.fragment), safe="")
        return prefix + escape(relative) + suffix + label + "</a>"
    return re.sub(r'(<a\b[^>]*?href=")(file://[^"]*)("[^>]*>)(.*?)</a>', replace, document, flags=re.S)


def generate(workspace: Path, output: Path, statuses: set[str] | None, archify: Path | None,
             *, snapshot: dict | None = None, max_age_minutes: float = 60,
             folder_scope: bool = False, web_root: Path | None = None) -> dict:
    import shlex

    if output.suffix.lower() != ".html":
        raise ValueError("dashboard output must have an .html extension")
    script = find_archify(archify)
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js is required to render the Archify task tree")
    snapshot = snapshot if snapshot is not None else collect(workspace, statuses, folder_scope=folder_scope)
    snapshot["max_age_minutes"] = max_age_minutes
    snapshot["web_root"] = str(web_root) if web_root else ""
    snapshot["output"] = str(output)
    inputs = fingerprint(snapshot)
    output.parent.mkdir(parents=True, exist_ok=True)
    git_ignore = exclude_generated(output)
    # A fresh evidence directory avoids overwriting earlier Archify receipts.
    evidence_root = output.parent / (output.stem + "-assets")
    evidence_root.mkdir(exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="render-", dir=evidence_root))
    source = evidence / "tasks.tree.json"
    source.write_text(json.dumps(tree_source(snapshot), indent=2) + "\n", encoding="utf-8")
    (evidence / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    env = {**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"}
    result = subprocess.run(
        [node, str(script), "finalize", "tree", str(source), str(evidence / "map.html"),
         "--quality", "showcase", "--json"],
        cwd=evidence, env=env, capture_output=True, text=True, check=False,
    )
    (evidence / "render.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise ValueError(f"Archify validation failed; previous dashboard kept. See {evidence / 'render.log'}")
    for name in ("LICENSE", "LICENSE-MIT", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        license_path = script.parent.parent / name
        if license_path.is_file():
            shutil.copy2(license_path, evidence / name)
    cli = Path(__file__).resolve().parents[3] / "scripts/agent-workspace.py"
    command = [sys.executable, str(cli), "dashboard", "--root" if folder_scope else "--workspace", str(workspace), "--output", str(output),
               "--refresh", "--max-age-minutes", str(max_age_minutes)]
    for status in sorted(statuses or []):
        command.extend(("--status", status))
    if archify:
        command.extend(("--archify", str(archify.expanduser().resolve())))
    if web_root:
        command.extend(("--web-root", str(web_root)))
    document = render(snapshot, (evidence / "map.html").read_text(encoding="utf-8"), shlex.join(command))
    if web_root:
        document = served_links(document, output, web_root)
    # Carry license text into the standalone document too.
    license_text = "\n\n".join((evidence / name).read_text(encoding="utf-8")
                                for name in ("NOTICE", "LICENSE", "LICENSE-MIT", "THIRD_PARTY_NOTICES.md")
                                if (evidence / name).is_file())
    document = document.replace("<!-- LICENSES -->", '<details class="licenses"><summary>Archify licenses and notices</summary><pre>' + escape(license_text) + '</pre></details>')
    atomic_write(output, document)
    atomic_write(metadata_path(output), json.dumps({
        "schema_version": 1, "generated_at": snapshot["generated_at"],
        "input_fingerprint": inputs, "output_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        "max_age_minutes": max_age_minutes, "workspace": str(workspace),
        "statuses": sorted(statuses or []), "folder_scope": folder_scope,
        "web_root": str(web_root) if web_root else "",
    }, indent=2) + "\n")
    return {"operation": "dashboard", "outcome": "complete", "output": str(output),
            "task_count": len(snapshot["tasks"]), "generated_at": snapshot["generated_at"],
            "evidence": str(evidence), "source": str(source), "freshness": "current",
            "max_age_minutes": max_age_minutes, "git_ignore": git_ignore}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--workspace", type=Path)
    scope.add_argument("--root", type=Path, help="include all registered tasks under this folder")
    parser.add_argument("--web-root", type=Path, help="HTTP server document directory")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--status", action="append", choices=tuple(STATUS_ORDER))
    parser.add_argument("--archify", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="check freshness without rendering or refreshing discovery")
    modes.add_argument("--refresh", action="store_true", help="refresh discovery and rebuild only when needed")
    parser.add_argument("--max-age-minutes", type=float, default=60)
    args = parser.parse_args()
    try:
        workspace = (args.root or args.workspace).expanduser().resolve()
        folder_scope = args.root is not None
        web_root = args.web_root.expanduser().resolve() if args.web_root else None
        if not workspace.is_dir():
            raise ValueError("task scope folder does not exist")
        output = (args.output or workspace / "outputs/task-dashboard.html").expanduser().resolve()
        if web_root and (not web_root.is_dir() or not output.is_relative_to(web_root)):
            raise ValueError("dashboard output must be inside the existing --web-root folder")
        if not math.isfinite(args.max_age_minutes) or args.max_age_minutes <= 0:
            raise ValueError("--max-age-minutes must be a positive finite number")
        if args.refresh:
            refresh_catalog(workspace, folder_scope=folder_scope)
        statuses = set(args.status) if args.status else None
        snapshot = None
        payload = None
        if args.check or args.refresh:
            snapshot = collect(workspace, statuses, folder_scope=folder_scope)
            snapshot["max_age_minutes"] = args.max_age_minutes
            snapshot["web_root"] = str(web_root) if web_root else ""
            snapshot["output"] = str(output)
            checked = check_report(output, snapshot, fingerprint(snapshot), args.max_age_minutes)
            if args.check:
                payload = checked
            elif checked["freshness"] == "current":
                payload = {**checked, "outcome": "unchanged", "git_ignore": exclude_generated(output)}
        if payload is None:
            payload = generate(workspace, output, statuses, args.archify,
                               snapshot=snapshot, max_age_minutes=args.max_age_minutes,
                               folder_scope=folder_scope, web_root=web_root)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
