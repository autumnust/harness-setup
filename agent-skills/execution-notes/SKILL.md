---
name: execution-notes
description: Prepare and maintain the observable execution environment for large, multi-step, or multi-session workloads. Use before starting a workload that needs a durable runbook, status dashboard, logs, evidence, stop/resume commands, or environment feasibility checks. Skip for small edits and one-off commands.
---

# Execution Notes

Make a workload feasible to run, observe, stop, and resume without relying on
chat history. This skill implements the execution-preparation role; it does not
own product implementation.

## When to use

Use this for large executions, expensive jobs, multi-stage validation, remote
workloads, or work likely to continue in another session. Skip it for a quick
fix, a single-file edit, or a command whose result can be reported immediately.

## Procedure

1. **Confirm the execution-folder location.** If the user or local repository
   has not chosen one, ask before creating files. Never guess a location or
   scatter artifacts around the repository.
2. **Create the minimum contract.** Follow the Long-Running Work Structure in
   `~/AGENTS.md`: a self-contained `README.md` or `SPEC.md`, one
   `progress.html`, and only the evidence, findings, or stage directories the
   workload actually needs.
3. **Inventory prerequisites.** Record the required runtime, services,
   credentials, datasets, ports, storage, remote hosts, and expected resource
   limits. Never persist secrets in the execution folder.
4. **Prove basic feasibility.** Run cheap, non-destructive checks for command
   availability, authentication presence, input accessibility, writable output
   paths, and service reachability. Do not start an expensive workload merely
   to prove the command exists.
5. **Write the operating path.** The runbook must contain exact commands to
   start, observe, stop safely, and resume. State where logs and outputs land,
   what success looks like, and how failure is recognized.
6. **Initialize observation.** Make `progress.html` show readiness, current
   stage, active blockers, next command, and links to available evidence.
7. **Validate the structure.** Invoke `work-structure-check` when available and
   fix structural findings before handing the environment to an executor.

## Return contract

Return only:

- execution-folder path;
- readiness: ready, partially ready, or blocked;
- exact next command;
- observation and stop commands;
- blockers or assumptions requiring the coordinator or user.

Do not claim readiness when a required credential, input, service, or safe stop
path has not been checked.
