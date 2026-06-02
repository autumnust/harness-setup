# Contents

- [Communication style](#communication-style)
  - [Lead explanations with concept, not code](#lead-explanations-with-concept-not-code)
  - [Self-check before sending an explanation](#self-check-before-sending-an-explanation)
- [Execution style](#execution-style)
- [Maintaining this file](#maintaining-this-file)

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
- **Use the words a reader from "Consumers background" would use.** This is the
  governing test for any term — verb, noun, or phrase. A term is suspect if it
  is *borrowed from a domain outside that background* (poker, clinical trials,
  an idiom) or is a *metaphor standing in for a mechanism*. When one is, replace
  it with the plain, literal word and say what actually happens. The lists below
  are illustrations of the habit, not the rule — a new word not listed here is
  caught by the same test.
  - figurative shorthand: "drop-in", "under the hood", "for free", "that's the
    tell" → state the mechanism ("you can't swap it in without changing X and Y";
    "the parameters exist but every path that uses them raises").
  - metaphorical verbs: "predict rides `fkey.pt`" → "predict loads from fkey.pt"
    (reads / calls / depends on — whichever it does); also "lives in", "talks to".
  - borrowed-domain nouns: "both arms" (trial/bandit) → "both branches" / "the
    two variants".
  - Worst case is a *conclusion* dressed as a flourish — end on what's literally
    true, not on an idiom.
- Spell out non-obvious abbreviations; if a response leans on several, add a
  short glossary up front.
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

### Example — naming the mechanism instead of a metaphor

❌ Figurative (avoid):

> The real coupling here — why it can't be a drop-in.

✅ Literal (prefer):

> Why you can't swap it in without other changes: its callers hand it a focus
> list and read back a filtered snapshot, so a replacement has to honor both
> sides or every caller breaks.

"Drop-in" sounds precise but names nothing; the rewrite says exactly what the
constraint is. If a phrase is a metaphor you couldn't define on request,
replace it with what actually happens.

## Self-check before sending an explanation

A quick pass before you hit send — any "yes" means rewrite:
- More backticks than verbs in the first paragraph? → it's been led by code;
  re-lead with what I'd notice.
- Any word — verb, noun, or phrase — borrowed from outside the Consumers
  background, or a metaphor standing in for a mechanism? ("drop-in", "rides",
  "arms", "the tell") → use the plain word and say what actually happens.
- Does a sentence end on a flourish or idiom instead of what's literally true?
  → end on the mechanism.
- Forced an analogy that doesn't cleanly map? → drop it; a wrong model is
  worse than none.
- Whiteboarded a direct question that wanted a one-line answer? → just answer.

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
