# PR-queue contract

The coordinator starts one PR maintainer for its lifetime. The maintainer owns
a persistent private queue under
`$AGENT_HARNESS_HOME/state/pr-queues/<coordinator-id>/`; the coordinator
registers each PR created by the execution by messaging the maintainer.

Each queue item records:

- PR URL, repository, base branch, and head branch;
- coordinator identity and responsible executor's routable identity;
- current merge, CI, review, and upstream-conflict state;
- last check, last notification signature, and terminal status.

The maintainer polls every configured interval, defaulting to 600 seconds, and
deduplicates unchanged notifications. It messages the registered executor
directly for repairable CI failures, upstream conflicts, or actionable review
items. It messages the coordinator for scope or user decisions, cross-PR
problems, terminal state, or an unavailable executor; a failed direct message
must fall back to the coordinator.

The maintainer never spawns an agent, edits product code, or talks to the human user. It
runs until the coordinator terminates, then stops cleanly. When a provider
cannot keep a background child active, the coordinator must resume the same
maintainer and its persisted queue on the configured cadence rather than create
independent monitors.
