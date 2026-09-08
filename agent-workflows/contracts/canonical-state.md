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

Agents may read GitHub, push their branches, create or update pull requests,
and change pull-request metadata when those actions are within the requested
work. They do not participate in pull-request review conversations: no review
submissions or review comments, and they do not reply to reviewers or resolve
review threads through the `gh` command line, the GitHub API, or a connected
MCP server. A child with a proposed review response returns the draft to the
coordinator. The coordinator gives that draft, or its own, to the human user
to post. Other GitHub operations follow the authority granted by the user's
request.
