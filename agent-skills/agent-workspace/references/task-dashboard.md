# Workspace task dashboard

This feature ships as a command in the harness, with instructions in the
[agent-workspace skill](../SKILL.md). The command generates an HTML file.
Archify renders the embedded task tree. No model call is needed to regenerate
the dashboard, and no background service runs after generation.

Generate a local HTML snapshot of registered workspace tasks:

```bash
agent-workspace dashboard --workspace /path/to/workspace --format json
agent-workspace dashboard --workspace /path/to/workspace --status active \
  --output /path/to/active-tasks.html --format json
```

The default destination is `outputs/task-dashboard.html` inside the workspace.
Repeat `--status` to include several statuses. Omit it to include all statuses.
The page opens with a compact task list. Switch to the interactive Archify tree
when needed. The list shows status, next action, update date, and
file links. Expand a task to read its full details. Search and status filters
apply to the list. The tree groups tasks by their folder and includes every
task location in the generated snapshot. Task filters do not change the tree.

The command uses the same workspace identity rules as `list-tasks`. It includes
registered tasks outside the workspace directory. It does not scan arbitrary
folders or infer membership from folder names. Import existing unregistered
tasks with `agent-task reconcile` before generating the dashboard.

Statuses and summaries come from the local catalog. These values describe the
last recorded task state, not live agents or processes. Each task shows the
catalog observation time. Missing folders remain visible. The command does not
change lifecycle state, create execution records, start agents, or schedule
refreshes. Run it again after task changes, then reload the page.

Rendering requires Node.js, the pinned Archify skill, and Chrome or Chromium
for Archify's browser validation. The generator finds installed Archify skill
directories automatically. Use `--archify /path/to/archify` to select an
explicit skill package. See the repository's
[external skill installation instructions](../../../README.md#adding-and-refreshing-external-skills).

The generated page embeds the Archify viewer and its license notices. Viewing
requires no server or network connection. Existing task file links work from
the local browser; they depend on the original task locations. Archify source,
snapshot data, notices, and validation receipts remain beside the page in a
`<dashboard-name>-assets` directory. Each render gets a separate subdirectory.
Rendering failures preserve the previous dashboard and report a diagnostic log.

The HTML and its assets contain local task names, paths, objectives, and next
actions. Keep them outside public source commits.

## Deploy and backfill on another machine

Install the updated harness on the destination through the normal
[deployment procedure](../../../README.md#keeping-a-machine-in-sync-after-the-repo-changes-repo--).
Deployment includes the command, template, skill instructions, and pinned
Archify package. It does not copy task folders or the source machine's catalog.
Python 3, Node.js, and Chrome or Chromium must be available on the destination
to generate and validate the page. Viewing the finished HTML needs only a browser.

Restore the workspace and its task folders on that machine before backfilling.
For example, a workspace may live at `/srv/work/project` while its existing
tasks live at `/srv/work/execution-notes`. Register both roots, then render:

```bash
agent-task reconcile /srv/work/project /srv/work/execution-notes --format json
agent-workspace list-tasks --workspace /srv/work/project -H
agent-workspace dashboard --workspace /srv/work/project --format json
```

The first command registers recognized workspace and task metadata in the
destination's local catalog. It preserves recorded lifecycle statuses. The
second command confirms membership before rendering. The last command writes
`/srv/work/project/outputs/task-dashboard.html` by default.

Tasks need recognized task metadata and a workspace identity. An arbitrary
notes folder does not become a task merely because it is under the workspace.
Keep existing task IDs and workspace IDs when copying tasks. For legacy tasks
that refer to a workspace path, make that reference valid on the destination.
The catalog does not infer a missing relationship from a matching folder name.

Repeat reconciliation after importing more folders or editing task records
outside the task commands. Regenerate the HTML after status changes. Reuse
the same output path. Deployment alone does not create or refresh dashboards.

The HTML is portable for reading. Task file links use the generation machine's
paths. Open it on that machine for working file links; copying the HTML alone
does not copy its linked task documents.
