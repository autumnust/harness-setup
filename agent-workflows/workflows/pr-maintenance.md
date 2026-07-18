# PR maintenance workflow

1. Resume the existing PR-maintainer agent when supported; otherwise provide
   its latest item ledger in a new context packet.
2. Refresh merge state, CI state, and unresolved review comments.
3. Resolve conflicts before debugging failures caused by the conflicted tree.
4. Address known comments in dependency order and keep item status explicit.
5. Re-run the narrow failing checks, then the broader checks required by the
   changed behavior.
6. Ask the coordinator for decisions that change scope or public behavior.
7. Close with an updated ledger and executor-mode retrospective.
