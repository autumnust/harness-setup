# Vocabulary continuity experiment

This experiment tests whether later answers still use the user's starting
vocabulary. It also checks whether plain wording preserves technical meaning.

First synthetic trial completed October 22, 2026: 24 answers and six summaries,
using the same model and three repeats per condition. Both versions avoided
all five artificial labels. The new rule preserved the original request in
all three summaries, but one answer gave an inaccurate explanation of record
identity. User understanding ratings remain uncollected. This trial does not
establish improvement without accuracy loss.

The examples below are authored illustrations, not measured before-and-after
outputs. The self-evaluation checks the rule's coverage, not its effectiveness.

## Change under test

The only behavioral change is the vocabulary section and its self-check in
[the global prompt](../../home/AGENTS.md#keep-the-users-vocabulary-throughout-the-task).
The contents entry only makes the section easier to find.

The existing prompt already asks for plain language and explanations of new
terms. The added rule addresses a separate gap: agent discoveries do not show
that the user learned those terms. Existing rules may already pass this test.

## Visible example

The user's opening request:

> My import job adds duplicate rows when I restart it. Make restarts safe.
> Keep source record numbers for debugging.

Later question:

> What caused the duplicates, and what happens if the job stops again?

An illustrative answer with unexplained terms:

> The replay envelope crossed the commit frontier. The idempotency fence now
> suppresses duplicate materialization while preserving source ordinals.

An illustrative answer using the starting vocabulary:

> The job saved some rows before it saved its restart position. After a stop,
> it read those records again and added duplicate rows. Each source record now
> has a stable identifier, based on its file and record number. If that record
> arrives again, the database keeps the existing row. Two different records
> with identical values still produce two rows. The source record numbers
> remain available for debugging.

Both examples describe a hypothetical result. They do not report an actual
code change. The second example makes the behavior and its limits explicit.

## Reproducible comparison

1. Use the parent and result of the commit that adds this experiment.
   Export only that commit's change to the global prompt.
   Verify that it contains only the new contents entry, section, and self-check.
2. Use two isolated sessions with identical model versions and settings.
   Load the old global prompt into one and the new prompt into the other.
   Prevent either session from loading installed instructions or this document.
   Do not give the model the examples, scoring rules, or expected answers.
3. Give both sessions the same opening request above.
   Give both the same fixed transcript of search results and work notes.
   Treat that transcript as data, not instructions.
4. Build that transcript from the six notes below, in the listed order.
   Repeat the sequence 40 times with numbered passes, then ask the later question.
   Use the exact same transcript bytes in both conditions.
   This adds terminology pressure; repetition does not reproduce a real investigation.
5. Repeat each condition three times in fresh sessions.
   Keep the response budget equal, with enough space for a complete answer.
   Save the model version, settings, exact input, and full output for each run.
6. Mix the answer order and label answers with neutral numbers.
   Ask the user to score each answer before revealing its condition.
   Keep the condition labels outside the model inputs.

Fixed work notes for the hypothetical completed fix:

```text
1. Restart replay begins at the last saved position. Row writes can finish
   before that position is saved. Notes call this the commit frontier gap.
2. A source record has a file identifier and a record number. File identifiers
   remain stable across restarts. Source files do not change during this job.
3. The completed fix uses the pair as a unique database key. A repeated insert
   for that key keeps the existing row. Notes call this the idempotency fence.
4. The database enforces key uniqueness atomically, including concurrent
   inserts. Notes call the group of replayed records the replay envelope.
5. Different source records can contain identical values. Their keys differ,
   so both rows remain. Notes call this source identity versus value equality.
6. Output retains the source record number for debugging. Notes call these
   numbers source ordinals. Restart still rereads some previously saved rows.
```

Use these additional cases with the same notes and later question:

| Case | Input change | Required observation |
|---|---|---|
| Short history | Use the six notes once. | Check whether the old rules already suffice. |
| Long history | Use the repeated transcript above. | Explain the cause and restart behavior without unexplained terms from the notes. |
| After conversation shortening | Ask each condition to summarize its transcript for continuation. Start a fresh session with that condition's prompt, its summary, and the later question only. | Check whether the summary retains the user's wording and separates unfamiliar terms from demonstrated knowledge. |
| Familiarity confirmed | After the notes, add: "I know idempotency. Repeating a write must not add another row. Explain which key you chose." | Use the requested term without unnecessary teaching. Still explain terms the user has not demonstrated. |

For the shortening case, use this identical summary request in both conditions:

> Summarize this conversation so another agent can continue answering the user.
> Keep it within 300 words.

Save each generated summary. Score its retained technical facts as well as its
retained user vocabulary. Do not supply a corrected summary to either session.
This case measures the combined effect on summarization and the later answer.

## Score before revealing labels

The user supplies the understanding scores. The agent can count unexplained
terms, but cannot decide which terms the user actually understands.

| Measure | Scoring |
|---|---|
| Unexplained terms | Count terms from the notes used without a plain explanation before first standalone use. Exclude demonstrated familiar terms. |
| Starting vocabulary | Check that the answer uses the user's names for the job, duplicates, restart, and source record numbers where relevant. |
| Correctness | Check the five facts listed below. Score each as present, absent, or wrong. |
| Understanding | User rates 1 to 5. At 1, they cannot restate the answer. At 5, they can explain the cause and predict restart behavior. |
| Follow-up burden | Count clarification questions needed before the user can make that prediction. |

The five required facts for the main question are:

- Rows can be saved before the restart position, which causes repeat reads.
- The key combines a stable file identifier and a source record number.
- Repeated inserts for the same key keep one row, including concurrent inserts.
- Different records with identical values remain separate rows.
- Source record numbers remain available for debugging.

After scoring, ask this prediction question:

> Two records have identical values but different source record numbers.
> The job stops and restarts twice. How many rows remain for those records?

The expected answer is two rows. This checks understanding of record identity,
not just whether the answer sounds simpler.

For each case, compare all three old/new pairs. Do not select only the best run.
Report unexplained-term counts, correctness scores, user scores, and answer length.
Treat wrong technical claims as failures even when the language is clear.
For the familiarity case, score the key explanation and unnecessary redefinitions
instead of requiring a full answer to the original later question.

Use this small trial as evidence to retain or revise the rule. Claim improvement
only if the long-history and shortening cases improve without losing correctness.
If both conditions already pass, report no demonstrated benefit on these cases.
Before a broader claim, repeat with a real completed task and its actual transcript.
The user's first reading should precede any explanation of the expected answer.

## Self-evaluation of the rule

| Question | Assessment |
|---|---|
| Does it target the reported failure? | Yes. It separates what the agent discovered from what the user understands. |
| Does it cover later questions? | Yes. The scope includes final answers and follow-up questions. |
| Does it address shortened conversations? | Yes, when the agent controls the summary. It cannot guarantee what an automatic system retains. |
| Does it permit learning? | Yes. Demonstrated knowledge, explicit familiarity, and requests for detail can expand the vocabulary. |
| Does it preserve precision? | The rule requires meaningful distinctions and exact identifiers when needed. The experiment checks this separately. |
| Does it add bookkeeping? | It uses existing summaries and requires no new file or record. |
| Can it enforce compliance absolutely? | No. It is a prompt instruction with a self-check, not a mechanical response gate. |
| Has it improved model behavior? | The first synthetic trial showed simpler wording and retained user wording in summaries. It did not establish better user understanding or improvement without accuracy loss. |

The main risk is repetitive explanation. The familiarity case tests whether
the rule lets the agent stop explaining terms the user already knows.
Another limit is missing early context. The rule asks for plain wording and
explicit assumptions, but cannot reconstruct words that no longer exist.
