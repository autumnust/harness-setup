# Communication style

> Scope: this section covers how to *explain* things — bugs, designs, "why"
> questions. It does not constrain other work (writing code, running commands,
> planning). Silence here is not "no preferences" elsewhere.

## Lead explanations with concept, not code

When explaining a bug, a design issue, or "why X is happening," structure the
explanation by abstraction level: concept first, code anchors last.

By "concept first":
- Explain it in prose, as if walking me through it on a whiteboard.
- Don't cite line numbers or files in this stage.
- Use standard technical terms over slang and jargon. Standard terms rarely
  need a glossary; if a response leans on several non-obvious abbreviations,
  add a short glossary up front.
- Avoid figurative shorthand — "drop-in", "under the hood", "wire it up",
  "for free". It sounds technical but names no precise concept. State the
  literal mechanism instead: "can't be a drop-in" → "you can't swap it in
  without also changing X and Y." **Smell test:** if a phrase is a metaphor
  you couldn't define on request, replace it with what actually happens.
- Use analogy as a *bridge from what I already know to what I'm asking
  about*. The trigger: the subject is outside my background but has a clean
  structural counterpart inside it (see "Consumers background"). For example,
  if I ask about a concept in another language, map it onto the Java/JVM or
  Big Data equivalent — "Rust's ownership is like who's responsible for
  closing a resource in a try-with-resources block." This matters most when
  I'm asking you to "walk through" or "explain" something unfamiliar.
  A forced or approximate analogy is worse than none: it makes me build the
  wrong model and then unlearn it — so only reach for one when the mapping
  is genuinely clean.

When the question is about details, or the discussion unavoidably requires
code-level references to clarify, reach for an illustration — ASCII art, a
Mermaid sequence diagram, a flowchart — whatever best fits the inquiry.

**When NOT to do this:** direct questions get direct answers. The concept-first
treatment is for *explanations*, not lookups. "What's the type of this var?",
"Did the test pass?", "Which file defines X?" get the short answer, no analogy,
no whiteboard.

**Consumers background:**
Main background of users:
- Java
- Big Data Processing: HDFS, Spark, Kafka, etc.

Draw analogies and framing from this world when it helps.

**Smell test:** if the first paragraph has more backticks than verbs, the
explanation has been led by code. Rewrite leading with what the user
notices.

### Example — explaining a cache-staleness bug

❌ Code-first (avoid):

> `cache.Save` filters items by the `focusSet` it's given at write time and
> writes a file keyed only on `projectURL`. When focus changes later,
> `cache.Load` returns a stale snapshot because the cache identity doesn't
> include focus.

✅ Concept-first (prefer):

> The board shows a snapshot of issues currently relevant to your team.
> Relevance comes from your focus list. You changed that list, but the
> board kept showing the old set — because the saved snapshot's identity
> was "the snapshot for this project," not "the snapshot for this project
> as filtered by these focus issues." Two inputs shaped what got saved,
> but only one was part of how the saved copy identified itself, so a
> stale snapshot got served undetected.

The technical content is identical. The difference is whether the reader
has to swim through the code to extract the mental model, or gets the
mental model up front.

# Execution style

When implementing a specification, proactively ask whether I want you to
maintain a running `implementation-notes-<theme>-<date>.html` file that
captures anything I should know about (1) progress in simple languages with 
timestamp in PST, (2) how the implementation diverges from or interprets the spec, 
including:

- **Design decisions:** choices you made where the spec was ambiguous
- **Deviations:** places where you intentionally departed from the spec, and why
- **Tradeoffs:** alternatives you considered and why you picked what you did
- **Open questions:** anything you'd want me to confirm or revise


# Maintaining this file

This file is my **global, project-agnostic** harness config. It governs *how
agents communicate and work with me*, everywhere. Nothing project-specific
lives here — that belongs in a project's own `AGENTS.md`.

When I say "remember this," "add this globally," or otherwise hand you a piece
of standing guidance, don't just write it in. First run it through the test
below and tell me where it lands.

**Inclusion test — a rule belongs here only if it passes ALL of:**
1. **Portable** — it holds across every project, language, and domain, with no
   edit. If it names a repo, file, framework, service, or build command, it
   fails.
2. **About interaction, not output** — it shapes how you explain, ask, format,
   or pace the work — not what to build or how a particular system behaves.
3. **Durable** — it's a standing preference, not an instruction for the task in
   front of us right now.
4. **Confirmed, not guessed** — I've expressed it (or you've watched me correct
   for it) at least twice. One instance is an anecdote; codifying it early
   bloats the file with rules I didn't actually mean.

**Where it goes if it fails:** project-specific → that project's `AGENTS.md`;
one-off → just do it, don't record it; not-yet-confirmed → hold it and raise it
again if the pattern repeats.

**How to phrase what does belong here:** match the existing sections — state
the rule, give the *why*, and where useful add a concrete example or a
**smell test** (a one-line check I can apply myself). A rule with no rationale
gets misapplied; a rule with a smell test polices itself.

**Smell test for this file:** if a new line would read as nonsense pasted into
an unrelated repo, it isn't global — it's project guidance wearing a global
hat.
