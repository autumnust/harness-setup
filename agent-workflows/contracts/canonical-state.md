# Canonical-state contract

The coordinator is the sole writer of shared, human-visible, or cross-goal
mutable state:

- runtime configuration and communication conventions;
- learner profiles and external-memory synchronization;
- the current `progress.html` and other canonical execution summaries;
- accepted changes proposed by the retrospector.

Children may write assigned product files, provision resources in their scope,
and store raw evidence or a private operational ledger in a disjoint location.
They must not update canonical state. A child returns a state-change proposal
with evidence; the coordinator validates and applies it without silently
changing the meaning. Retrospector output is always a proposal, and the
coordinator obtains the human user's approval before applying any proposed process,
prompt, skill, runbook, or harness change.

Outbound GitHub conversation is written by the human user alone, including
the coordinator's own turns. This covers pull-request and issue comments,
review submissions and replies, and review-thread resolution. Every role may
read GitHub and may push its own branches. No role posts, replies, or
resolves, whether through the `gh` command line, the GitHub API, or a
connected MCP server. A child with something to say returns the drafted text
to the coordinator. The coordinator presents that draft, or its own, to the
human user to post.
