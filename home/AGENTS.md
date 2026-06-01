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
captures anything I should know about how the implementation diverges from or
interprets the spec, including:

- **Design decisions:** choices you made where the spec was ambiguous
- **Deviations:** places where you intentionally departed from the spec, and why
- **Tradeoffs:** alternatives you considered and why you picked what you did
- **Open questions:** anything you'd want me to confirm or revise
