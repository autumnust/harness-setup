# PR review workflow

Full-mode only.

1. Coordinator assembles the review context: the problem statement, user
   decisions, linked design material, repository guidance, and the complete
   branch diff target.
2. Coordinator sends that context and the implementation provider, foundation,
   concrete model, and identity to Reviewer in a `mode: full` packet.
3. Reviewer invokes the provider adapter's cross-provider backend exactly
   once, passes that context to it, and waits for its opinion. No other role
   may invoke that backend. Reviewer does not perform a second same-foundation
   review.
4. Return the opinion's findings, its model provenance, and external command
   status. If the backend is unavailable, return a blocked result.
5. Coordinator reports the findings. When the user already wanted merge-ready
   work, Coordinator assigns accepted corrections to Executor.

## Result

- **Finding:** one item from the other-foundation opinion, with severity,
  evidence, and expected correction when the opinion provides them.
  Reviewer does not add a second review or manufacture findings.

## Required review scope

The other-foundation opinion should cover:

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- whether changes were made in the correct place or use a workaround;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

An optional supporting scanner may cover style, naming, documentation,
duplication, generated-file noise, dependency noise, and broad low-risk scans.
A supporting scan never replaces the other-foundation opinion.
