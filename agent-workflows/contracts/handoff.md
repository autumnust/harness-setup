# Handoff contract

Every delegated assignment must provide enough context to succeed without
access to the parent's conversation history. Include:

- **Mode:** `fast` or `full`. Fast packets omit review-only Executor
  provenance and PR-Maintainer routing. A requested PR is full work.
- **Goal:** the concrete outcome and why it matters.
- **User intent:** relevant user wording, preferences, and decisions.
- **Scope:** owned files or systems, plus explicit exclusions.
- **Constraints:** applicable instructions, safety limits, and depth remaining.
- **Runtime configuration:** only the resolved values relevant to this child.
- **Current state:** branch, diff, completed work, failures, and dirty files.
- **Routing:** coordinator identity and the child's routable identity.
- **Artifacts:** clickable links or paths to specifications and evidence.
- **Open questions:** unresolved assumptions the child should investigate.
- **Return contract:** expected result, word limit, and required evidence.

The child must state any missing context that materially limits confidence. It
must not silently invent a user decision. The coordinator either passes the
packet directly or persists it in the configured canonical location; children
do not create a competing shared context packet.
