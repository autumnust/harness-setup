# PR-queue contract

Each Coordinator identity has one persistent private queue under
`$AGENT_HARNESS_HOME/state/pr-queues/<coordinator-id>/`.

Each queue item records:

- PR URL, repository, base branch, and head branch;
- coordinator identity and responsible executor's routable identity;
- current merge, CI, review, and upstream-conflict state;
- last check, last notification signature, and terminal status.

Each notification contains the PR identity, observed state transition,
evidence, requested action, and deduplication signature.

Only Coordinator registers queue items. Only Maintainer writes the private
queue. Maintainer follows the PR-maintenance workflow for polling,
notification routing, provider fallback, and lifecycle.
