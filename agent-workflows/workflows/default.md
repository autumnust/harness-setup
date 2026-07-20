# Default workflow

1. The coordinator resolves runtime configuration and starts one background PR
   maintainer for its lifetime.
2. The coordinator decides whether delegation materially improves the task.
3. For long-running execution, the coordinator creates canonical entry points
   and sends the resolved environment packet to `exec-env-prepper`.
4. The prepper returns readiness. The coordinator presents it to Lei and waits
   for confirmation or forwards follow-up preparation before implementation.
5. The coordinator sends a bounded context packet to the executor. The executor
   returns verification, model provenance, routable identity, and every PR URL.
6. The coordinator registers PRs with the maintainer and selects a reviewer
   from a different model foundation. A plan-level review may run earlier for a
   risky design under the same independence rule.
7. Operational roles may recommend educator or retrospective work. Only the
   coordinator decides and invokes those paths. For interactive education, the
   coordinator registers one stable educator session, presents its first turn,
   routes Lei to the direct thread, and waits for explicit completion.
8. The coordinator reconciles results, applies permitted canonical-state
   updates, and reports the outcome to Lei.
