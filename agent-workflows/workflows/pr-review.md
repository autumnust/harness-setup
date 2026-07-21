# PR review workflow

1. Read the PR problem statement, linked design material, repository guidance,
   and the complete branch diff.
2. Review the problem and approach before reviewing individual lines.
3. Include executor provider, foundation, concrete model, and identity. Select a
   configured primary reviewer from a different foundation or report blocked.
4. Give public interfaces, new features, and changed core logic to the primary
   reviewer. Use the configured supporting backend only for eligible scanning.
5. Verify supporting-tool findings and deduplicate them against primary review.
6. Return an education-mode recommendation and the actual reviewer provenance
   to the coordinator; the reviewer does not spawn another agent.
7. Return findings first, ordered by severity, then open questions and residual
   test risk. Do not manufacture findings to fill a category.
