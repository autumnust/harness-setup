---
name: execution-notes
description: Prepare and validate the observable execution environment for large, multi-step, remote, hardware-dependent, or multi-session workloads. Use from the execution-environment-prepper after the coordinator resolves configuration and creates canonical entry points. Skip for small edits and one-off commands.
---

# Execution Notes

Make a workload feasible to run, observe, stop, and resume without relying on
chat history. This skill implements execution preparation and includes the
deterministic structure checker that previously existed as a separate skill.

## When to use

Use this for large executions, expensive jobs, multi-stage validation, remote or
special-hardware workloads, or work likely to continue in another session. The
context packet must contain resolved runtime configuration, an authorized
execution path, and coordinator-owned canonical entry points. Report missing
values to the coordinator; never ask the user directly.

## Procedure

1. **Validate authority and paths.** Use only the execution path, evidence
   location, and resource scope authorized in the context packet. Do not create
   or update `progress.html`, learner state, global configuration, or another
   canonical artifact.
2. **Inventory prerequisites.** Record runtimes, credentials, datasets, ports,
   storage, services, remote hosts, accelerators, memory, quotas, and expected
   limits. Never persist secrets.
3. **Provision the environment.** Within the authorized scope, prepare
   directories, services, dependencies, remote machines, and special hardware.
   Stop before any destructive, expensive, or unapproved action.
4. **Prove feasibility.** Run cheap checks for command availability,
   authentication presence, input accessibility, writable output paths,
   service reachability, resource capacity, and safe shutdown. Do not start an
   expensive workload merely to prove the command exists.
5. **Record scoped evidence.** Write raw readiness evidence only in the assigned
   location. Return proposed canonical runbook or dashboard changes to the
   coordinator instead of publishing them yourself.
6. **Define operation.** Return exact start, observe, stop, and resume commands,
   output locations, success signals, and failure signals.
7. **Validate structure.** Run:

   ```bash
   python3 <this-skill-directory>/scripts/check_work_structure.py <execution-folder>
   ```

   Use `--json` for structured findings and `--strict` to treat warnings as
   failures. Fix only non-canonical paths you own; propose canonical fixes to
   the coordinator. Rule provenance is in `references/RULES.md`.

## Return contract

Return only:

- execution-folder path;
- readiness: ready, partially ready, or blocked;
- exact next command;
- observation and stop commands;
- blockers or assumptions requiring the coordinator or user.
- canonical-state changes the coordinator should publish.

Do not claim readiness when a required credential, input, service, hardware
resource, or safe stop path has not been checked. The coordinator presents the
readiness report to the user and decides whether execution may begin.
