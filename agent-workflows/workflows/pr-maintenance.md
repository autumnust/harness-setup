# PR maintenance workflow

1. The coordinator starts one maintainer and keeps its identity until the
   coordinator terminates.
2. Whenever the execution creates a PR, the coordinator sends a registration
   containing the PR and responsible executor's routable identity.
3. The maintainer persists the queue and polls all nonterminal items every
   configured interval, defaulting to ten minutes.
4. It compares merge state, CI, upstream conflicts, and unresolved review items
   with the prior snapshot and deduplicates unchanged notifications.
5. It messages the registered executor for repairable failures and the
   coordinator for decisions, cross-PR issues, terminal state, or failed direct
   delivery.
6. The executor reports repairs to the coordinator; the maintainer verifies the
   next observed state rather than trusting a completion claim.
7. On runtimes without durable background children, the coordinator resumes the
   same maintainer and persisted queue on schedule.
8. The maintainer stops when the coordinator terminates.
