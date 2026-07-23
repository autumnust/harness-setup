# Agent topology

The main session is always the coordinator and is the human user's sole
interface. It owns interactive education, spawning, decisions, canonical
state, and final synthesis. Every operational child is a leaf.

```mermaid
flowchart TB
    Human["Human user"] <-->|all interactive decisions| Coordinator

    subgraph Agents["Agent sessions"]
        Coordinator["Coordinator<br/>depth 0<br/>root and education mode"]

        subgraph Leaves["Operational children: depth 1, leaves"]
            Prep["Environment Prepper<br/>execution readiness"]
            Executor["Executor<br/>implementation<br/>provider model at high effort"]
            Reviewer["Reviewer<br/>adversarial review<br/>Executor model at max effort"]
            Maintainer["PR Maintainer<br/>lazy-started<br/>coordinator lifetime"]
        end
    end

    Coordinator -->|spawn with context packet| Prep
    Coordinator -->|assign bounded change| Executor
    Coordinator -->|request two-judgment review| Reviewer
    Coordinator -->|start for PR-producing work| Maintainer

    Maintainer -.->|queue and PR status| Coordinator
    Maintainer -.->|message only the registered identity| Executor

    subgraph Review["Reviewer reconciliation"]
        Opinion(["Cross-provider opinion<br/>invoked only by Reviewer"])
        Agreement["Agreed result"]
        Contested["Contested result<br/>Both positions and evidence"]
    end

    Reviewer -->|invoke exactly once and wait| Opinion
    Opinion -->|independent findings| Reviewer
    Reviewer -->|both judgments accept| Agreement
    Reviewer -->|only one judgment accepts| Contested
    Agreement -->|return| Coordinator
    Contested -->|return for human assessment| Coordinator
    Coordinator -->|assign accepted work| Executor
    Coordinator -->|ask for assessment| Human

    subgraph Tools["Invoked capabilities: not agents"]
        Retrospector(["Retrospector skill"])
        Scanner(["Optional supporting scanner"])
    end

    Coordinator -.->|invoke after evidence| Retrospector
    Reviewer -.->|mundane checks only| Scanner
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
