# Agent topology

The main session is always the coordinator and is the human user's sole
interface. It owns interactive education, spawning, decisions, canonical
state, and final synthesis. Every operational child is a leaf.

```text
coordinator (depth 0)
|-- exec-env-prepper (depth 1, leaf)
|-- executor (depth 1, leaf)
|-- reviewer (depth 1, leaf)
`-- pr-maintainer (depth 1, leaf; lazy-started, then coordinator-lifetime)

retrospector: a coordinator-invoked skill; it is not another agent
cross-provider review: invoked only by Reviewer; it is not another agent
supporting scanner: an optional configured tool; it is not another agent
```

## Rules

1. All current children are depth-one leaves. Keep the provider limit at depth
   two as a defensive ceiling; it is not permission for a child to spawn.
2. Only the coordinator spawns agents, enters education mode, or invokes the
   retrospector skill.
3. The coordinator delegates only when isolation, parallelism, special model
   choice, or reduced context noise materially improves the work.
4. Parallel writers must own disjoint files. Otherwise, serialize the work.
5. A child receives an explicit context packet. Provider-native conversation
   inheritance is an optimization, not a requirement.
6. Children normally message only the coordinator. The sole peer-message
   exception is PR maintainer to the exact executor identity registered for a
   queue item, with coordinator fallback when delivery fails.
7. Children do not accept direct human turns. The coordinator remains the
   interactive teaching interface while education mode is active.
8. Education mode may reuse a relevant existing child or spawn a new child for
   bounded evidence collection, experiments, or teaching artifacts. The child
   returns material to the coordinator and does not teach the human user
   directly.
9. The coordinator owns final synthesis and every user-visible decision.
