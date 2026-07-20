# Interactive education-session contract

The coordinator is Lei's default interface. The educator is the sole exception:
Lei may interact directly with one educator only while the coordinator has
registered an active education session. This exception does not transfer
orchestration, approval, canonical-state, or learner-state authority to the
educator.

## Start and handoff

1. The coordinator creates a unique session ID, records the topic, educator
   identity, current learner-profile revision, and `active` state under:

   ```text
   $AGENT_HARNESS_HOME/state/education-sessions/<session-id>.json
   ```

   The record must conform to
   `$AGENT_HARNESS_HOME/specs/education-session.schema.json`. Only the
   coordinator writes it.

2. Only one educator may be active for a coordinator. Spawn it with the stable
   display name `Educator`, a complete context packet, and the session ID.
3. The educator returns one bounded initial explanation or question with
   `status: awaiting-human`.
4. The coordinator presents that initial content and tells Lei how to open the
   exact educator thread using the active provider's adapter instructions. The
   coordinator remains active and registers a waiter for educator results.
5. When direct child interaction is unavailable, use the same protocol through
   transparent coordinator relay. Do not silently drop the teaching session.

## Interactive loop

Lei may answer, redirect, request a different depth, pause, or say that the
session is done directly in the educator thread. The educator keeps the same
session ID and returns exactly one of these statuses after each turn:

- `awaiting-human`: continue the same session; this is not completion.
- `education-complete`: Lei ended the session normally; return the closure
  payload below.
- `education-paused`: preserve the session for later resumption and do not
  propose a learner-state update yet.
- `education-abandoned`: close without a learner-state update.
- `blocked`: direct interaction or required context failed.

The coordinator may receive intermediate child-turn notifications while Lei is
interacting with the educator. It does not republish or close the lesson for an
`awaiting-human` result; it returns to waiting. A provider lifecycle stop event
is only a wake-up signal because an ordinary conversational turn may also stop.
Only an explicit education status determines session completion.

## Completion callback

For `education-complete`, the educator returns:

- session ID and educator identity;
- concepts explored;
- demonstrated understanding and the evidence for it;
- remaining gaps or likely misconceptions;
- a replacement learner-profile proposal, or `none`;
- retrospection evidence; and
- the reason Lei ended the session.

The provider's native child-result, direct-message, or idle notification wakes
the waiting coordinator. The coordinator validates the result, records the
terminal session state, decides whether the evidence meets the learning-state
contract, and asks Lei before persisting a material or uncertain profile
change. Only the coordinator writes learner state or synchronizes external
memory.
