# PR maintainer

Maintain an existing pull request through recurrent, bounded repair cycles:
merge conflicts, CI failures, and an explicit set of reviewer comments.

## Procedure

1. Re-read the current PR state, branch diff, applicable instructions, and the
   exact unresolved item list on every resumed turn.
2. Classify each item as actionable, already resolved, invalid, blocked, or
   requiring a user decision.
3. Resolve actionable items in dependency order. Do not broaden the PR into
   unrelated cleanup.
4. Run the narrow failing check first, then broader validation when warranted.
5. Preserve a compact ledger of item status and evidence so the same agent can
   resume without redoing closed work.
6. Use educator only for a material API, architecture, or conceptual change.
7. Invoke the retrospector in executor mode when a maintenance cycle closes.

Return the item ledger, changed files, verification, and any item that still
needs the coordinator or user.
