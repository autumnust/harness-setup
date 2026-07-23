# Default workflow

1. Coordinator classifies the goal and selects the applicable workflow.
   Education requests follow the education-mode workflow instead of the
   operational sequence below.
2. For operational work, the coordinator resolves the required runtime
   configuration and decides whether delegation materially improves the task.
3. For long-running execution, the coordinator creates canonical entry points
   and sends the resolved environment packet to `exec-env-prepper`.
4. The prepper returns readiness. The coordinator presents it to the human user
   and waits for confirmation or forwards follow-up preparation before
   implementation.
5. The coordinator sends a bounded context packet to the executor. The executor
   returns verification, model provenance, routable identity, and every PR URL.
6. PR-producing or PR-monitoring work follows the PR-maintenance workflow.
   Work requiring review follows the PR-review workflow. A plan-level review
   may run earlier for a risky design.
7. Operational roles may return education or retrospective recommendations.
   Coordinator routes education through the education-mode workflow and alone
   invokes retrospector.
8. The coordinator reconciles results, applies permitted canonical-state
   updates, and reports the outcome to the human user.
