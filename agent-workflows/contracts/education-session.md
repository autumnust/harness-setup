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
3. Follow the active provider adapter:
   - **Direct-thread mode:** the educator sends one bounded initial explanation
     or question to the coordinator with `status: awaiting-human` without
     returning, then enters the provider's live wait primitive.
   - **Coordinator-relay mode:** the educator returns that bounded
     `awaiting-human` turn to the coordinator and becomes idle. The coordinator
     presents it and ends its own turn so Lei regains the input UI.
4. In direct-thread mode, the coordinator tells Lei how to open the educator
   and waits for messages or a terminal result. In relay mode, it tells Lei that
   replies will be forwarded to the same educator identity on the next
   coordinator turn.
5. When direct child interaction is unavailable, use the same protocol through
   transparent coordinator relay. Do not silently drop the teaching session.

## Interactive loop

Lei may answer, redirect, request a different depth, pause, or say that the
session is done directly in the educator thread. The educator keeps the same
session ID and uses one of these statuses:

- `awaiting-human`: a nonterminal state. In direct-thread mode, send it without
  returning and re-enter the provider wait primitive. In coordinator-relay
  mode, return it to the coordinator, become idle, and resume the same educator
  identity when the coordinator forwards Lei's next response.
- `education-complete`: Lei ended the session normally; return the closure
  payload below.
- `education-paused`: preserve the session for later resumption and do not
  propose a learner-state update yet.
- `education-abandoned`: close without a learner-state update.
- `blocked`: direct interaction or required context failed.

In direct-thread mode, respond to Lei as an intermediary update and re-enter the
provider wait primitive after each nonterminal turn. In coordinator-relay mode,
return one compact teaching turn at a time; the coordinator publishes it,
releases the UI, and resumes the exact same educator identity with Lei's next
response. Do not spawn a replacement educator for each turn. Neither mode
closes the lesson for `awaiting-human`. Only an explicit terminal education
status determines session completion.

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
