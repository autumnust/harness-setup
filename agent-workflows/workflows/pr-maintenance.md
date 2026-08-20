# PR maintenance workflow

Full-mode only.

1. Coordinator starts one Maintainer when full work first creates or monitors
   a PR and retains its identity until Coordinator terminates.
2. For every created or adopted PR, Coordinator sends a registration satisfying
   the PR-queue contract, including the responsible Executor's routable
   identity.
3. Maintainer persists the queue and polls all nonterminal items every
   configured interval, defaulting to ten minutes.
4. Maintainer compares merge state, CI, upstream conflicts, and unresolved
   review items with the prior snapshot and emits no notification when the
   signature is unchanged.
5. Maintainer selects one notification route using the definitions below.
6. Executor reports repairs to Coordinator. Maintainer closes an item only
   after observing the resolved state; a completion claim alone is not enough.
7. On runtimes without durable background children, the coordinator resumes the
   same maintainer and persisted queue on schedule.
8. The maintainer stops when the coordinator terminates.

## Notification routes

- **Registered Executor route:** repairable CI failures, upstream conflicts,
  and actionable review items go directly to the exact Executor identity
  stored on that queue item.
- **Coordinator route:** scope or user decisions, cross-PR problems, terminal
  state, and failed direct delivery go to Coordinator. A failed Executor
  message always falls back to this route.
