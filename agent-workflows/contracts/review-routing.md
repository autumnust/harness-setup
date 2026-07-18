# Review routing contract

The reviewer retains responsibility for material judgment even when another
tool performs a supporting scan.

## Reviewer-owned work

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

## CodeRabbit-eligible work

- style and naming consistency;
- documentation nits and obvious duplication;
- generated-file or dependency noise;
- broad low-risk scans that the reviewer subsequently verifies.

## Educator trigger

Engage the educator when the change introduces an important API or architecture
concept, requires a user decision, reveals a learner-profile gap, or Lei asks
to understand the reasoning. Do not engage it for mechanical repairs.

A cross-foundation second opinion requires an explicitly configured external
CLI or MCP backend. A native child agent alone does not guarantee provider
diversity. Report which backend actually performed the review.
