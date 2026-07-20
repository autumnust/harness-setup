# Review routing contract

The reviewer retains responsibility for material judgment even when a
configured supporting-review backend performs a scan.

## Reviewer-owned work

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

## Supporting-backend work

- style and naming consistency;
- documentation nits and obvious duplication;
- generated-file or dependency noise;
- broad low-risk scans that the reviewer subsequently verifies.

The backend comes from resolved runtime configuration; no product is assumed or
hardcoded. The reviewer verifies and deduplicates its findings before returning
them. Supporting scans never satisfy the independent primary-review requirement.
