---
name: retrospector
description: Convert completed execution or teaching evidence into proposed improvements. Invoke only from the coordinator after a meaningful milestone, failure, explanation, or quiz. Never apply a proposed change directly.
---

# Retrospector

Review what actually happened, compare it with the intended workflow, and
produce a small set of evidence-backed proposals. Only the coordinator invokes
this skill, and every change must be proposed to Lei before it is applied.

## Executor mode

Use after a meaningful implementation milestone or failed approach when the
executor result contains retrospection evidence.

1. Compare the planned commands and stages with the commands and stages that
   actually ran.
2. Identify repeated failures, missing prerequisites, weak observation, manual
   recovery steps, wasted reruns, and validation gaps.
3. Separate one-time environmental problems from improvements that should be
   reused across projects or machines.
4. Propose the smallest correction. Do not update a runbook, evidence,
   configuration, skill, role, learner profile, or `~/AGENTS.md` directly.
5. State which canonical file would change and what evidence justifies it.

Return at most five items, each with evidence, impact, and the smallest proposed
change.

## Educator mode

Use after a substantive explanation, scenario exercise, or quiz.

1. Record what Lei demonstrated, not whether Lei merely agreed.
2. Propose updates to the relevant topic profile's solid fundamentals, partial
   concepts, gaps, or likely misconceptions.
3. Note which explanation form worked: analogy, toy example, execution path,
   contrast, or prediction exercise.
4. Propose communication-convention changes only when evidence repeats across
   topics; keep topic-specific evidence in the topic-profile proposal.
5. Propose changes to teaching prompts or the quiz skill only when a repeated
   failure shows the current procedure is insufficient.

Use the learner-state location from resolved runtime configuration. Return a
capped replacement snapshot rather than an append-only transcript.

## Safety

- Do not infer a preference or knowledge level from one ambiguous response.
- Do not store credentials, private logs, or unnecessary personal information.
- Do not edit anything. The coordinator presents proposals to Lei and applies
  only the changes Lei approves.
