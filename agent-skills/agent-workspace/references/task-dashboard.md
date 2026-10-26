# Workspace task dashboard

Generate a local HTML snapshot of registered workspace tasks:

```bash
agent-workspace dashboard --workspace /path/to/workspace --format json
agent-workspace dashboard --workspace /path/to/workspace --status active \
  --output /path/to/active-tasks.html --format json
```

The default destination is `outputs/task-dashboard.html` inside the workspace.
Repeat `--status` to include several statuses. Omit it to include all statuses.
The page includes searchable task cards, status filters, file links, and an
interactive Archify tree grouped by task folder. The tree includes every task
location in the generated snapshot. Card filters do not change the tree.

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
