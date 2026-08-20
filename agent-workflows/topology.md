# Agent topology

The main session is always the coordinator and is the human user's sole
interface. It owns interactive education, spawning, decisions, canonical
state, and final synthesis. Every operational child is a leaf. Fast is the
default path; full is escalation.

```mermaid
flowchart TB
    Human["Human user"] <-->|all interactive decisions| Coordinator

    subgraph Fast["Fast path: default"]
        Coordinator["Coordinator<br/>depth 0<br/>root and education mode"]
        Executor["Executor<br/>worktree, high effort"]
        Coordinator -->|0-N disjoint scopes| Executor
    end

    subgraph Full["Full path: escalation"]
        Prep["Environment Prepper"]
        Reviewer["Reviewer<br/>other-foundation opinion"]
        Maintainer["PR Maintainer"]
        Opinion(["Cross-provider opinion"])
    end

    Coordinator -->|long-running only| Prep
    Coordinator -->|review / merge-ready| Reviewer
    Coordinator -->|PR-producing work| Maintainer
    Reviewer -->|invoke once and wait| Opinion
    Opinion -->|findings| Reviewer
    Reviewer -->|return opinion| Coordinator
    Maintainer -.->|queue and PR status| Coordinator
    Maintainer -.->|registered identity only| Executor

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
2. Only Coordinator spawns agents. Retrospector and supporting scanners are
   invoked capabilities, not children.
3. Children normally message only Coordinator. The sole peer-message
   exception is PR maintainer to the exact executor identity registered for a
   queue item.
4. Children do not accept direct human turns. Coordinator remains the sole
   default human interface.
5. Diagram edge labels summarize behavior. The Coordinator prompt and shared
   workflow files define process order, lifecycle, and result routing.
