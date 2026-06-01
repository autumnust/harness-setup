# Communication style

## Lead explanations with concept, not code

When explaining a bug, a design issue, or "why X is happening," structure the
explanation by abstraction level: concept first, code anchors last. 
By "concept first": 
- Try to explain everything in prose as if you are walking
me through it on a whiteboard. 
- Don't cite line number or files in this stage.
- Use a concise analogy to help users understand the explanation. See 
"Consumers background" for more information.
- Use standard technical terms, instead of slangs and jargon. When using
abbreviation: Make sure creating a glossary section upfront.

When user asked about details, or the discussion will unavoidably requires 
referencing code-level details to clarify / assist understanding, use illustration
tool like ascii-art, mermaid diagram to draw sequencing diagram, flowchart or 
other good way of illustration best practice based on user's inquiries.

**Consumers background:**
Main background of users:
- Java
- Big Data Processing: HDFS, Spark, Kafka etc. 

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
When implementing a specification, practively ask user if they want agent to maintain a running implementation-notes-<theme>-<dates>.html file that captures anything user should know about how the implementation diverges from or interprets the spec, including:

- Design decisions: choices you made where the spec was ambiguous
- Deviations: places where you intentionally departed from the spec, and why
- Tradeoffs:  alternatives you considered and why you picked what you did
- Open questions: anything you'd want user to confirm or revise