# PR review workflow

1. Read the PR problem statement, linked design material, repository guidance,
   and the complete branch diff.
2. Include executor provider, foundation, concrete model, and identity in the
   Reviewer context packet.
3. The Reviewer invokes the provider adapter's cross-provider backend exactly
   once. No other role may invoke that backend for review.
4. Give problem framing, public interfaces, new features, and changed core
   logic to that primary review. Use a configured supporting scanner only for
   eligible mundane checks.
5. Verify evidence references and deduplicate supporting-tool findings against
   the primary review without replacing its material judgment.
6. Return an education-mode recommendation and the actual reviewer provenance
   to the coordinator; the reviewer does not spawn another agent.
7. Return findings first, ordered by severity, then open questions and residual
   test risk. Do not manufacture findings to fill a category.
