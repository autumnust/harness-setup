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
3. The educator sends one bounded initial explanation or question to the
   coordinator with `status: awaiting-human` without returning or ending its
   turn. It then enters the provider's live wait primitive and remains active.
4. The coordinator receives that nonterminal message, presents its content, and
   tells Lei how to open the exact educator thread using the active provider's
   adapter instructions. The coordinator also remains active and waits for
   educator messages or terminal results.
5. When direct child interaction is unavailable, use the same protocol through
   transparent coordinator relay. Do not silently drop the teaching session.

## Interactive loop

Lei may answer, redirect, request a different depth, pause, or say that the
session is done directly in the educator thread. The educator keeps the same
session ID and uses one of these statuses:

- `awaiting-human`: a nonterminal message or live state. Never return it as the
  child result. Continue the same session and re-enter the provider wait
  primitive after responding.
- `education-complete`: Lei ended the session normally; return the closure
  payload below.
- `education-paused`: preserve the session for later resumption and do not
  propose a learner-state update yet.
- `education-abandoned`: close without a learner-state update.
- `blocked`: direct interaction or required context failed.

While selected in the educator thread, respond to Lei as an intermediary update
and then re-enter the provider wait primitive. Do not emit a final response,
return a child result, or become idle merely because one teaching turn ended.
The coordinator may receive intermediate notifications but does not republish
or close the lesson for `awaiting-human`; it returns to waiting. A provider
lifecycle stop event is only a wake-up signal. Only an explicit terminal
education status determines session completion.

## Completion callback

For `education-complete`, the educator exits the wait loop and returns:

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
