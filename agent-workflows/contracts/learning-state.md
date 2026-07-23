# Learning-state contract

Mutable learning state lives at the configured provider-neutral location. The
portable fallback is:

```text
$AGENT_HARNESS_HOME/state/learner-profiles/<topic>.md
$AGENT_HARNESS_HOME/state/communication.md
```

`AGENT_HARNESS_HOME` defaults to `~/.agent-harness`. Only the coordinator writes
learner state. Entering education mode loads the relevant current profile; the
coordinator and quiz procedure collect evidence and prepare a proposed
replacement snapshot. Outside education mode, do not load or update a profile
unless the human user explicitly requests that exact state operation.

A topic profile is a current snapshot, not an append-only transcript. Keep:

- solid fundamentals that no longer need introductory explanation;
- partial concepts that work in common cases but fail under variation;
- gaps where no working model is demonstrated;
- likely misconceptions, with the evidence that exposed them;
- the last meaningful evidence date.

Do not infer mastery from agreement or silence. Update a profile only from a
scenario answer, an explanation in the user's own words, a concrete decision,
or another clear demonstration. The coordinator synchronizes an external
memory backend only when runtime configuration selects one. The local files
remain the portable fallback unless the human user chooses a different source of truth.
At education-mode exit, apply `learner_profile_update_policy` from runtime
configuration: `ask`, `auto`, or `off`. A missing value means `ask`. Even under
`auto`, ask the human user before persisting a material or uncertain change.
