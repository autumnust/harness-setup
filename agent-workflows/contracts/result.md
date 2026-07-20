# Child-result contract

Every child returns a compact result to its permitted parent or message target:

- **Status:** complete, blocked, or needs-decision.
- **Outcome:** what changed or what was learned.
- **Evidence:** commands, artifacts, findings, or links supporting the result.
- **Blockers and decisions:** items requiring the coordinator or Lei.
- **Model provenance:** provider, foundation, concrete model, and agent identity.
- **State proposals:** requested canonical-state updates, with evidence.
- **Education recommendation:** yes or no; if yes, the topic and reason.
- **Retrospection input:** meaningful failures, reruns, or teaching evidence.

Omit fields that genuinely do not apply, but never omit model provenance from
executor or reviewer results. A child does not claim user-visible completion.
The coordinator sequences the next role and publishes the final result.
