# Agent topology

The main session is always the coordinator and is the only agent that talks to
Lei by default. Work flows outward as bounded assignments and returns as capped
summaries. Agents do not depend on peer-to-peer messaging for correctness.

```text
coordinator (depth 0)
|-- exec-env-prepper (depth 1)
|   `-- educator (depth 2)
|-- executor (depth 1)
|   `-- educator (depth 2)
|-- reviewer (depth 1)
|   `-- educator (depth 2)
|-- pr-maintainer (depth 1)
|   `-- educator (depth 2)
`-- educator (depth 1)

retrospector: a skill used by executor and educator; it is not another agent
CodeRabbit: an optional reviewer tool; it is not another agent
```

## Rules

1. Maximum nesting depth is two below the coordinator.
2. Any depth-one operational agent may engage the educator. Depth-two agents
   are leaves and must not spawn another agent.
3. The coordinator delegates only when isolation, parallelism, special model
   choice, or reduced context noise materially improves the work.
4. Parallel writers must own disjoint files. Otherwise, serialize the work.
5. A child receives an explicit context packet. Provider-native conversation
   inheritance is an optimization, not a requirement.
6. Child agents return results to their parent. The coordinator owns final
   synthesis and user-visible decisions.
