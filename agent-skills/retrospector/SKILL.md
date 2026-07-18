---
name: retrospector
description: Convert completed execution or teaching evidence into concrete improvements. Use in executor mode after a meaningful milestone, failure, or PR-maintenance cycle; use in educator mode after a substantive explanation or quiz. Do not run after every small action and do not silently edit the global harness.
---

# Retrospector

Review what actually happened, compare it with the intended workflow, and
produce a small set of evidence-backed improvements. Choose exactly one mode.

## Executor mode

Use after a meaningful implementation milestone, closed PR-maintenance cycle,
or failed approach that exposed an execution problem.

1. Compare the planned commands and stages with the commands and stages that
   actually ran.
2. Identify repeated failures, missing prerequisites, weak observation, manual
   recovery steps, wasted reruns, and validation gaps.
3. Separate one-time environmental problems from improvements that should be
   reused across projects or machines.
4. Update the execution runbook or evidence when the correction is local to the
   current workload.
5. Propose, but do not automatically make, changes to global skills, agent
   roles, or `~/AGENTS.md`.

Return at most five items, each with evidence, impact, and the smallest proposed
change.

## Educator mode

Use after a substantive explanation, scenario exercise, or quiz.

1. Record what Lei demonstrated, not whether Lei merely agreed.
2. Update the relevant topic profile's solid fundamentals, partial concepts,
   gaps, or likely misconceptions.
3. Note which explanation form worked: analogy, toy example, execution path,
   contrast, or prediction exercise.
4. Update communication conventions only when evidence repeats across topics;
   keep topic-specific evidence in the topic profile.
5. Propose changes to teaching prompts or the quiz skill only when a repeated
   failure shows the current procedure is insufficient.

Use `$AGENT_HARNESS_HOME/state/learner-profiles/`, defaulting
`AGENT_HARNESS_HOME` to `~/.agent-harness`. Keep each profile a capped current
snapshot rather than an append-only transcript.

## Safety

- Do not infer a preference or knowledge level from one ambiguous response.
- Do not store credentials, private logs, or unnecessary personal information.
- Do not edit the global harness unless the user separately asks for that
  change.
