# Contents

- [Communication style](#communication-style)
  - [Lead explanations with concept, not code](#lead-explanations-with-concept-not-code)
  - [Resolve domain-ambiguous terms before acting](#resolve-domain-ambiguous-terms-before-acting)
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
- **Calibrate explanation to my familiarity.** By default, assume I don't know
  this codebase: the first time you use a term specific to it (or an unusual
  one), explain it in one short plain phrase. If I say I'm familiar with a
  component, cut the explanations for that component and stay terse there.
- **Ground data-heavy or structural topics in a tiny worked example.** For
  things like indexing, file layouts (e.g. the fkey file), joins, partitioning,
  or encodings, don't explain in prose alone — make up the smallest concrete
  data that shows the behavior (a few rows, a handful of keys), then walk the
  mechanism through it and show the before/after state. The toy example is what
  makes the operation visible.
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

For code-level "how does this flow / where does X happen" questions, a cascaded
call stack in ASCII is usually clearest: indent each call under its caller so
nesting shows depth, branch with `├─`/`└─`, and annotate the frame where the
behavior of interest happens.

```
handle_predict(req)
└─ Model.predict(df, pos=…, length=…)
   ├─ _validate_args(pos, length)        ← raises here if pos/length passed (line 656)
   └─ _run_batch_prediction_ttng(df)
      └─ partition(df, num_partitions)    ← raises unless num_partitions == 1
```

When a return value or data flows back up matters, show it too:

```
load_user(id)                     → User
└─ db.query("SELECT … WHERE id=?") → Row | None
   └─ Row(...)                     → returned to load_user, wrapped as User
```

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

## Resolve domain-ambiguous terms before acting

Some technical terms carry meaningfully different definitions across domains.
Examples:

| Term | Possible meanings |
|------|-------------------|
| "driver" | device driver, database driver, Spark driver, UI test driver |
| "partition" | OS disk partition, Kafka partition, Spark RDD partition, DB shard |
| "executor" | Java thread pool, Spark worker node, CI job runner |
| "broker" | Kafka broker, message broker, network proxy |

When a user message contains a term like these and the surrounding context does
not pin down which meaning applies, **do not guess — ask one short clarifying
question before proceeding.** A silent assumption that turns out wrong produces
work built on the wrong foundation; a one-sentence question costs almost nothing.

**When to ask:** the term has two or more distinct technical definitions, and
substituting one for another would produce meaningfully different work.

**When NOT to ask:** the codebase, the open file, or the conversation already
makes the meaning unambiguous — proceed, and note which meaning you used.

**Smell test:** could you write two different one-sentence answers — each
correct under a different definition — that point at completely different work?
If yes, surface the ambiguity before acting.

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
- Used a codebase-specific or unusual term, for a component I haven't said I
  know, without a one-phrase plain gloss? → define it inline.
- Explaining a data-heavy or structural topic (indexing, file layout, joins)
  in prose only? → add a tiny worked example with toy data.
- Explaining code-level call flow without showing it? → add an ASCII call-stack
  cascade, annotating the frame where the behavior of interest happens.
- About to act on a term that carries different meanings across technical
  domains, and context doesn't resolve which one? → ask before acting.

# Execution style

This applies only to **large, multi-step** executions — a multi-part feature, a
migration, anything spanning more than one session. **Skip all of it for small
or spotty changes** (a quick fix, a single-file tweak, a one-off): the overhead
isn't worth it there. For the large ones, keep a small set of running artifacts
so the work stays auditable as it goes:

- **Pick an execution folder first.** All the files below live in one folder. If
  I start an execution without telling you where, proactively ask before
  creating anything — don't scatter files across the repo or guess a location.
- **Link all references.** Any generated HTML or Markdown file that references
  another file, section, PR, or external resource must use a clickable
  hyperlink — never bare text. Generated files are read in a rendered context
  (browser, Markdown viewer), so bare paths and names are dead ends. When the
  referenced item lives in a code repository, link to the repo (e.g. a GitHub
  permalink to the file, line, commit, or PR) — not just the local path.
- **`implementation-notes-<theme>-<date>.html`** — a running record of how the
  implementation diverges from or interprets the spec:
  - **Design decisions:** choices you made where the spec was ambiguous
  - **Deviations:** places where you intentionally departed from the spec, and why
  - **Tradeoffs:** alternatives you considered and why you picked what you did
  - **Open questions:** anything you'd want me to confirm or revise
  - **Pending PRs / merge dependencies:** a dedicated section for pull requests,
    review branches, or external changes needed to make the execution fully green.
    Include links, what each PR unblocks, the exact failure or gap it addresses,
    and any producer/consumer evidence that explains why the change belongs there.
- **`progress-<theme>-<date>.html`** — a running progress chart in plain
  language, each entry timestamped in PST. Whenever a ticket or PR is involved,
  reference it here as a clickable hyperlink.


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
