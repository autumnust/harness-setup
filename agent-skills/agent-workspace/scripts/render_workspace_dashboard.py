#!/usr/bin/env python3
"""Render a read-only workspace task snapshot with an embedded Archify tree."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from catalog_client import list_records
from list_workspace_tasks import STATUS_ORDER, discover
from start_workspace_task import workspace_identity


ASSETS = Path(__file__).resolve().parent.parent / "assets"


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


def collect(workspace: Path, statuses: set[str] | None) -> dict:
    name, _ = workspace_identity(workspace / "workspace.yaml")
    tasks, _ = discover(workspace, statuses)
    # Discovery owns workspace identity, including legacy and external locations.
    records = {(r.get("id"), r.get("path")): r
               for r in list_records("--kind", "workspace-task")}
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
        "workspace": str(workspace), "workspace_name": name,
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


def generate(workspace: Path, output: Path, statuses: set[str] | None, archify: Path | None) -> dict:
    import shlex

    if output.suffix.lower() != ".html":
        raise ValueError("dashboard output must have an .html extension")
    script = find_archify(archify)
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js is required to render the Archify task tree")
    snapshot = collect(workspace, statuses)
    output.parent.mkdir(parents=True, exist_ok=True)
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
    command = [sys.executable, str(cli), "dashboard", "--workspace", str(workspace), "--output", str(output)]
    for status in sorted(statuses or []):
        command.extend(("--status", status))
    if archify:
        command.extend(("--archify", str(archify.expanduser().resolve())))
    document = render(snapshot, (evidence / "map.html").read_text(encoding="utf-8"), shlex.join(command))
    # Carry license text into the standalone document too.
    license_text = "\n\n".join((evidence / name).read_text(encoding="utf-8")
                                for name in ("NOTICE", "LICENSE", "LICENSE-MIT", "THIRD_PARTY_NOTICES.md")
                                if (evidence / name).is_file())
    document = document.replace("<!-- LICENSES -->", '<details class="licenses"><summary>Archify licenses and notices</summary><pre>' + escape(license_text) + '</pre></details>')
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as pending:
        temporary = Path(pending.name)
        pending.write(document)
    try:
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"operation": "dashboard", "outcome": "complete", "output": str(output),
            "task_count": len(snapshot["tasks"]), "generated_at": snapshot["generated_at"],
            "evidence": str(evidence), "source": str(source)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--status", action="append", choices=tuple(STATUS_ORDER))
    parser.add_argument("--archify", type=Path)
    args = parser.parse_args()
    try:
        workspace = args.workspace.expanduser().resolve()
        output = (args.output or workspace / "outputs/task-dashboard.html").expanduser().absolute()
        payload = generate(workspace, output, set(args.status) if args.status else None, args.archify)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
