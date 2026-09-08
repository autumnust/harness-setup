---
name: execution-notes
description: Prepare and validate an explicit agent-workspace task's execution environment. Use from the execution-environment-prepper only after the user selects agent-workspace and the coordinator provides its task folder.
---

# Execution Notes

Make a workload feasible to run, observe, stop, and resume without relying on
chat history. This skill implements execution preparation and includes the
deterministic structure checker that previously existed as a separate skill.

## When to use

Use this only for a task the user explicitly started through `agent-workspace`.
A large change, several repositories, remote hardware, multiple sessions, or
full mode does not select this skill by itself. The context packet must contain
the workspace task folder, resolved runtime configuration, and coordinator-owned
canonical entry points. Report missing values to the coordinator; never ask the
user directly or create another execution folder.

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
