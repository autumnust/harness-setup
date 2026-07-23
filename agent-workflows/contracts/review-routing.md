# Review routing contract

The configured cross-provider backend returns the first review opinion. The
Reviewer is the sole owner of invoking it, waiting for completion, and then
challenging it with a full review from the executor's model foundation at the
highest configured effort.

## Both judgments cover

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

## Reconciliation

- Agreement means both judgments accept the same finding as valid and
  actionable. Return it under **Suggested action items** with severity,
  evidence, and expected correction. The coordinator selects an executor.
- Disagreement means only one judgment accepts a finding, including a finding
  discovered only by Reviewer. Return it under **Disagreements** with both
  positions, their evidence, and the decision required. The coordinator asks
  the human user to assess it before implementation.
- Absence from one opinion is not automatic disagreement until Reviewer checks
  the claim explicitly.

## Optional supporting-scanner work

- style and naming consistency;
- documentation nits and obvious duplication;
- generated-file or dependency noise;
- broad low-risk scans that the reviewer subsequently verifies.

The external backend comes from the provider adapter. A supporting scanner may
come from runtime configuration. Its findings follow the same reconciliation
rule and never replace either full judgment.
