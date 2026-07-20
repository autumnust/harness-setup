# Child-result contract

Every child returns a compact result to its permitted parent or message target:

- **Status:** complete, blocked, or needs-decision. A registered educator uses
  the additional education-session statuses defined in its contract.
- **Outcome:** what changed or what was learned.
- **Evidence:** commands, artifacts, findings, or links supporting the result.
- **Blockers and decisions:** items requiring the coordinator or Lei.
- **Model provenance:** provider, foundation, concrete model, and agent identity.
- **State proposals:** requested canonical-state updates, with evidence.
- **Education recommendation:** yes or no; if yes, the topic and reason.
- **Retrospection input:** meaningful failures, reruns, or teaching evidence.

Omit fields that genuinely do not apply, but never omit model provenance from
executor or reviewer results. A child does not claim workflow-level completion.
During a registered education session, the educator may present teaching turns
directly to Lei, but only the coordinator closes the session, applies state
changes, and publishes the overall result.
