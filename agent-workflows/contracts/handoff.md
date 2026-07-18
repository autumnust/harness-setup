# Handoff contract

Every delegated assignment must provide enough context to succeed without
access to the parent's conversation history. Include:

- **Goal:** the concrete outcome and why it matters.
- **User intent:** relevant user wording, preferences, and decisions.
- **Scope:** owned files or systems, plus explicit exclusions.
- **Constraints:** applicable instructions, safety limits, and depth remaining.
- **Current state:** branch, diff, completed work, failures, and dirty files.
- **Artifacts:** clickable links or paths to specifications and evidence.
- **Open questions:** unresolved assumptions the child should investigate.
- **Return contract:** expected result, word limit, and required evidence.

The child must state any missing context that materially limits confidence. It
must not silently invent a user decision. For long-running work, persist a
compact current packet under the execution folder's `evidence/` directory; for
small tasks, pass it directly in the delegation prompt.
