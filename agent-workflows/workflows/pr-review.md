# PR review workflow

1. Read the PR problem statement, linked design material, repository guidance,
   and the complete branch diff.
2. Include executor provider, foundation, concrete model, and identity in the
   Reviewer context packet.
3. The Reviewer invokes the provider adapter's cross-provider backend exactly
   once and waits for its opinion. No other role may invoke that backend.
4. Reviewer then performs a full adversarial review using the same model as
   Executor at the highest configured effort.
5. Reviewer returns agreed findings as **Suggested action items**. The
   coordinator selects an executor and sends those items for correction.
6. Reviewer returns every finding accepted by only one judgment as
   **Disagreements**, with both positions and evidence. The coordinator asks
   the human user to assess each disagreement before assigning work.
7. Return an education-mode recommendation and both model provenances; Reviewer
   does not spawn another agent. Do not manufacture findings to fill a category.
