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
4. **Persist the result as a learner profile, in a fixed global location** —
   not the per-project auto-memory system. Auto-memory is keyed to whichever
   repo you're sitting in (`~/.claude/projects/<cwd>/memory/`), but
   understanding of a subject like a language feature or design pattern isn't
   repo-specific and shouldn't reset every time you `cd` somewhere else.
   Write to `~/.claude/learner-profiles/<topic>.md` (create the directory and
   file if they don't exist yet), regardless of which tool or project you're
   running in.
   - **Before quizzing**, check whether a profile for the topic already
     exists and treat it as the starting point, not a blank slate — skip
     re-probing what it already marks as a solid fundamental unless the
     user's answers this session contradict it.
   - **After quizzing**, update the file in place with this session's
     findings rather than appending a new dated entry — this is a living
     snapshot of current understanding, not a history log.
   - This file isn't limited to `/quiz` — any agent that gets clear evidence
     the profile is stale (the user demonstrates a gap it marked solid, or
     masters something it marked as a gap) should update it, not just this
     skill.
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
Codex CLI.
