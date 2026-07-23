---
name: quiz
description: Interview the user with scenario-based questions on a subject to find out what they actually understand — not just what they can define — then calibrate later explanations to that assessed level. Use when the user says "grill me on X", "quiz me on X", or invokes /quiz X.
---

# Quiz

Two goals, in order: (1) give the user a way to check their own understanding
of a subject, and (2) build an accurate picture of where they stand so later
explanations land at the right depth instead of over- or under-explaining.

## When to use

Triggered by "grill me on X", "quiz me on X", or `/quiz X`. `X` is whatever
subject the user names — a language feature, a design pattern, a piece of
this codebase, anything.

## How it works

1. **Interview first, in scenarios, not definitions.** Ask questions that
   require predicting behavior in a concrete situation ("given this queue and
   these two writers, what happens if...?"), not questions that can be
   answered by reciting a definition ("what is a mutex?"). A user can define
   a term correctly while still misapplying it — scenario questions catch
   that; definition questions don't.
2. **Ask several before concluding.** One question tells you almost nothing.
   Cover the common case, then push into at least one edge case or failure
   mode before forming a judgment.
3. **Classify the answers**, not just score them right/wrong:
   - **solid fundamentals** — correct and confidently applied under variation
   - **partial concepts** — right in the common case, breaks under a twist
   - **gaps** — no working model at all
   - **likely misconceptions** — a confident, wrong model (more useful to
     find than a gap, since it actively steers future answers wrong)
4. **Return a learner-profile proposal to the coordinator** rather than writing
   mutable state. Resolve the current profile location from the coordinator's
   runtime configuration; the portable fallback is
   `$AGENT_HARNESS_HOME/state/learner-profiles/<topic>.md`, with
   `AGENT_HARNESS_HOME` defaulting to `~/.agent-harness`.
   - **Before quizzing**, check whether a profile for the topic already
     exists and treat it as the starting point, not a blank slate — skip
     re-probing what it already marks as a solid fundamental unless the
     user's answers this session contradict it.
   - **After quizzing**, propose a complete replacement snapshot rather than an
     appended dated entry. Include the evidence for every changed assessment.
   - Any agent that sees clear contradictory evidence reports a proposal to the
     coordinator. Only the coordinator writes learner state or synchronizes an
     external-memory backend.
5. **Use the profile immediately, same session.** The next explanation of
   this subject should skip what's a solid fundamental, confirm/repair what's
   partial, and start from scratch on gaps — per the existing "calibrate
   explanation to my familiarity" rule in `~/AGENTS.md`'s Communication style
   section.
6. **Keep explanations within the assessed concept budget.** Don't dump
   everything the model knows about the subject once the quiz is over —
   answer at the depth the interview just established, and expand only when
   asked.

## Relationship to `~/AGENTS.md`

`~/AGENTS.md` carries a short pointer to this skill (Learning Calibration
Mode) so tools without Agent Skills support still know the behavior exists in
outline; this file is the full protocol, invoked as `/quiz` in Claude Code or
Codex CLI. When invoked in the main session, the coordinator performs the
write-authority portion after validating the proposal.
