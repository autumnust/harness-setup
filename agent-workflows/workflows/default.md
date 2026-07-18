# Default workflow

1. The coordinator decides whether delegation materially improves the task.
2. For long-running execution, the coordinator confirms an execution-folder
   location and runs `exec-env-prepper` before implementation.
3. The coordinator sends bounded context packets to the required roles.
4. The executor or PR maintainer implements and verifies its owned scope.
5. The reviewer assesses the approach and material code after enough work
   exists to review. A plan-level review may run earlier for risky designs.
6. Reviewer, executor, or coordinator engages educator only under the routing
   contract.
7. The coordinator reconciles results, updates the one progress entry point
   when applicable, and reports the outcome to Lei.
