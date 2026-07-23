# Review routing contract

The configured cross-provider backend performs the material primary review.
The Reviewer is the sole owner of invoking it and returning its findings
faithfully. The Reviewer may verify evidence and remove exact duplicates, but
its low-latency router model must not replace the external review judgment.

## Primary cross-provider review

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

## Optional supporting-scanner work

- style and naming consistency;
- documentation nits and obvious duplication;
- generated-file or dependency noise;
- broad low-risk scans that the reviewer subsequently verifies.

The primary backend comes from the provider adapter. A supporting scanner may
come from runtime configuration. Supporting scans never satisfy the
cross-provider primary-review requirement.
