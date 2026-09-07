---
name: crash-recovery
description: Recover local task and workspace discovery after a reboot, moved folders, or a lost runtime; check TSS separately only when requested.
---

# Crash recovery

Task context survives runtime loss. Start with the local catalog:

```bash
task-catalog list --format json
```

After an old installation or a manual copy or move, repair registrations and
list again:

```bash
task-catalog reconcile <root> [<root> ...] --format json
```

These operations do not contact or recreate TSS sessions. If the user asks for
a live runtime check, use TSS directly, such as `tss <host>` to list that host's
sessions. Start a replacement only after explicit intent, using the
`task-session` runtime route. A replacement restores the task working directory,
not old processes, panes, buffers, or an agent conversation.

Never change task lifecycle state because a runtime is missing.
