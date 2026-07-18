# Learning-state contract

Mutable learning state lives outside provider-specific configuration:

```text
$AGENT_HARNESS_HOME/state/learner-profiles/<topic>.md
$AGENT_HARNESS_HOME/state/communication.md
```

`AGENT_HARNESS_HOME` defaults to `~/.agent-harness`.

A topic profile is a current snapshot, not an append-only transcript. Keep:

- solid fundamentals that no longer need introductory explanation;
- partial concepts that work in common cases but fail under variation;
- gaps where no working model is demonstrated;
- likely misconceptions, with the evidence that exposed them;
- the last meaningful evidence date.

Do not infer mastery from agreement or silence. Update a profile only from a
scenario answer, an explanation in the user's own words, a concrete decision,
or another clear demonstration. An external memory MCP may mirror this state,
but the local files remain the portable fallback unless the user chooses a
different source of truth.
