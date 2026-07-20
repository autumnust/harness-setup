# Default workflow

1. The coordinator classifies the goal. Education-only requests leave this
   workflow immediately and use `workflows/education.md`.
2. For operational work, the coordinator resolves the required runtime
   configuration and decides whether delegation materially improves the task.
3. For long-running execution, the coordinator creates canonical entry points
   and sends the resolved environment packet to `exec-env-prepper`.
4. The prepper returns readiness. The coordinator presents it to Lei and waits
   for confirmation or forwards follow-up preparation before implementation.
5. The coordinator sends a bounded context packet to the executor. The executor
   returns verification, model provenance, routable identity, and every PR URL.
6. When the workflow can create or monitor a PR, the coordinator starts one
   background PR maintainer for its remaining lifetime. It registers created
   PRs and selects a reviewer from a different model foundation. A plan-level
   review may run earlier for a risky design under the same independence rule.
7. Operational roles may recommend educator or retrospective work. Only the
   coordinator decides and invokes those paths. For interactive education, the
   coordinator registers one stable educator session, presents its first turn,
   routes Lei to the direct thread, and waits for explicit completion.
8. The coordinator reconciles results, applies permitted canonical-state
   updates, and reports the outcome to Lei.
