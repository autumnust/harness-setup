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
coordinator obtains Lei's approval before applying any proposed process,
prompt, skill, runbook, or harness change.
