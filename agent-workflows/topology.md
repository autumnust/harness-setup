# Agent topology

The main session is always the coordinator and is Lei's sole default interface.
It owns spawning, decisions, canonical state, and final synthesis. Every
operational child is a leaf. The educator is the only role eligible for a
scoped direct-human exception during a coordinator-registered education
session; providers without a nonblocking child UI use coordinator relay.

```text
coordinator (depth 0)
|-- exec-env-prepper (depth 1, leaf)
|-- executor (depth 1, leaf)
|-- reviewer (depth 1, leaf)
|-- pr-maintainer (depth 1, leaf; lazy-started, then coordinator-lifetime)
`-- educator (depth 1, leaf; registered direct-human session)

retrospector: a coordinator-invoked skill; it is not another agent
supporting reviewer: a configured tool/backend; it is not another agent
```

## Rules

1. All current children are depth-one leaves. Keep the provider limit at depth
   two as a defensive ceiling; it is not permission for a child to spawn.
2. Only the coordinator spawns agents or invokes educator and retrospector
   paths.
3. The coordinator delegates only when isolation, parallelism, special model
   choice, or reduced context noise materially improves the work.
4. Parallel writers must own disjoint files. Otherwise, serialize the work.
5. A child receives an explicit context packet. Provider-native conversation
   inheritance is an optimization, not a requirement.
6. Children normally message only the coordinator. The sole peer-message
   exception is PR maintainer to the exact executor identity registered for a
   queue item, with coordinator fallback when delivery fails.
7. Only the educator may accept direct human turns, and only while its
   coordinator-registered session is active and the provider adapter supports a
   nonblocking child UI. Otherwise the coordinator relays turns to the same
   educator identity. Neither mode grants state-write or workflow-completion
   authority.
8. The coordinator owns final synthesis and every user-visible decision.
9. An education-only goal uses only coordinator and educator. It does not start
   execution, review, environment-preparation, or PR-maintenance roles.
