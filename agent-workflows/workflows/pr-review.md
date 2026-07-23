# PR review workflow

1. Read the PR problem statement, linked design material, repository guidance,
   and the complete branch diff.
2. Include executor provider, foundation, concrete model, and identity in the
   Reviewer context packet.
3. Reviewer invokes the provider adapter's cross-provider backend exactly
   once and waits for its opinion. No other role may invoke that backend.
4. Reviewer then performs a full adversarial review using the same model as
   Executor at the highest configured effort.
5. For every finding from either review, Reviewer tests the claim explicitly.
   Absence from one opinion is not a difference until Reviewer checks it.
6. Classify each tested finding using the result categories below.
7. Return an education-mode recommendation and both model provenances. Reviewer
   does not spawn another agent or manufacture findings to fill a category.

## Result categories

- **Suggested action item:** both judgments accept the finding as valid and
  actionable. Reviewer includes severity, evidence, and expected correction.
  Coordinator selects an Executor and sends the item for correction.
- **Disagreement:** only one judgment accepts the finding, including a finding
  discovered only by Reviewer. Reviewer includes both positions, their
  evidence, and the exact decision required. Coordinator asks the human user
  to assess it before assigning work.

## Required review scope

Both judgments cover:

- problem framing and whether the approach is sound;
- public API, protocol, schema, and compatibility changes;
- whether changes were made in the correct place or use a workaround;
- new user-visible behavior;
- architecture, security, concurrency, and data correctness;
- changed core logic, regressions, and missing behavioral tests.

An optional supporting scanner may cover style, naming, documentation,
duplication, generated-file noise, dependency noise, and broad low-risk scans.
Reviewer tests its findings through the same result classification. A
supporting scan never replaces either full judgment.
