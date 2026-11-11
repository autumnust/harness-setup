---
name: mr-walkthrough
description: Write a structured walkthrough of a merge request or pull request — glossary, problem, solution shape with toy examples and call stacks, an assessment with corner cases and the author's open decisions, and a close. Use when the user asks to walk through, explain, summarize, assess, or review a merge request or pull request, given as a URL, a number, or a branch.
---

# MR walkthrough

Explain one merge request (MR) or pull request (PR) as one story. The reader
must understand the problem, the shape of the solution, and the weak points
without reading the diff first.

This skill writes text for the user. Do not post it to the MR or PR. If the
user wants it posted, give them the text to post.

## Gather the inputs first

Read all of these before writing:

- the MR or PR description,
- the changed files, with their added and removed line counts,
- the commit titles,
- the full text of the core changed files, not only the diff,
- the top-level `README.md`, to decide which terms need no glossary entry.

Use the tool that the host gives you. Examples:

| Host | Commands |
|---|---|
| GitHub | `gh pr view <n>`, `gh pr diff <n>` |
| GitLab | `glab mr view <n>`, or the REST API with a token |
| Local branch | `git log --oneline <base>..<head>`, `git diff --stat <base>...<head>` |

If you cannot read an input, say which input is missing at the start of the
walkthrough.

## How to write

- Follow the user's global communication rules when they exist. Otherwise
  use short sentences, active voice, and one idea in each sentence.
- Keep each diagram and code block 60 characters wide or less.
- Use the section headings below, in this order.
- Find the main change by its effect on behavior, not by the order of
  commits or files. A small change to docs or config must not hide a larger
  change to code.
- Write every section and every Assessment part. If a part does not apply,
  write "Not applicable" and one reason.

## 0. Glossary

Give 8 entries at most. Include a term only if both are true:

- It is not common technical knowledge.
- The top-level `README.md` does not define it.

Give each term a one-line plain meaning. If more than 8 terms qualify, keep
the 8 that the walkthrough needs most. Explain the others inline.

## 1. The problem

- What the user or the system could not do before.
- The workaround that people used, and why it was bad.
- One sentence for the goal.

## 2. The solution shape

Use numbered steps with one idea each. Describe the change with primitives:
APIs, scripts, files, functions, rules, and storage locations. Mark each new
public-facing API as new. Leave out line-level detail.

Each step has:

- one sentence for the idea,
- a toy example, a small table, or a diagram next to it,
- a call stack when the step describes code flow, with `← new` and
  `← here` marks.

Example of a call stack:

```
cmd_submit(args)
├─ find_covering_audit(run)   ← new
└─ ingest(bundle)
   └─ refuse_checkpoints()    ← here
```

Put the steps in causal order. Each step answers the question that the step
before it raises. Use a diagram only where it helps.

## 3. Assessment

Use these parts in this order.

1. **Verdict on the core.** Is the main idea sound? Is it hacky?
2. **Root cause of complexity.** One sentence on why the code is heavy.
3. **Corner cases.** Numbered items. For each item, give:
   - what the code does, with `file:line`,
   - why it exists, and how rare the case is,
   - a simpler option.
4. **Decisions the author asks for.** Each question or decision in the
   description, for example under "For the reviewer". For each one, give:
   - the decision in one sentence,
   - the options and the cost of each,
   - your recommendation, with one reason.

   If the author asks nothing, say so in one line.
5. **Scope creep.** Behavior changes outside both the MR title and the
   problem that the MR claims to solve.
6. **Alternative design not considered.** One paragraph with its cost and
   its benefit.

## 4. Close

- Name what the walkthrough does not cover.
- Offer one next step.
