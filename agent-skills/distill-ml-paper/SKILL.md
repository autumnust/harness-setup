---
name: distill-ml-paper
description: Distill a machine-learning paper into its central research idea, evidence, computational behavior, and infrastructure consequences. Use when Codex needs to triage, explain, compare, critique, or create an engineering brief for an ML paper, especially for tabular learning, foundation models, training systems, inference, performance, scaling, or production readiness.
---

# Distill ML Paper

Convert a paper into a small, testable model of what it changes and what that
change requires from data and systems. Do not attempt to restate the entire
paper.

## Choose the reading mode

Select the least expensive mode that answers the user's question:

- **Quick triage — 15 minutes:** Retain or skip the paper; output its claim,
  evidence type, relevance, and recommended engagement level.
- **Standard brief — 60–120 minutes:** Explain the research idea, smallest
  example, training and inference flows, main evidence, and limitations.
- **Systems brief — 2–4 hours:** Add tensor dimensions, state, compute, memory,
  data movement, scaling behavior, profiling targets, and production judgment.
- **Research critique:** Add assumptions, alternative explanations, missing
  experiments, and proposed follow-ups. Use only when the user is implementing,
  reviewing, or co-developing the method.

Default to a systems brief for an infrastructure engineer unless the user asks
for another mode.

## Collect the evidence

1. Read the primary paper. Prefer the publisher or arXiv version.
2. Read supplementary material only when the main paper delegates a required
   method or evaluation detail to it.
3. Inspect official code or model documentation when the task asks about actual
   execution, configuration, tensor dimensions, or serving behavior.
4. Record section, figure, table, appendix, and code references as clickable
   links when the source format permits.
5. State when a required source is inaccessible. Do not reconstruct missing
   content from unrelated summaries.

## Distillation workflow

### 1. Fix the question and engagement level

Write the user's decision in one sentence. Example: “Determine whether this
model can serve 10,000-row contexts within a 24 GB GPU.”

Assign a level:

- **0 — vocabulary:** Define the term and give one example.
- **1 — mental model:** Explain the problem, core idea, and why it matters.
- **2 — architecture:** Trace inputs, components, training, inference, tensor
  flow, and basic scaling.
- **3 — mathematical and systems:** Analyze the main objective, computation,
  memory, implementation constraints, and evaluation.
- **4 — research critique:** Test assumptions, propose alternatives, and design
  decisive experiments.

Use level 2 for most relevant papers, level 3 for foundational or
infrastructure-critical papers, and level 4 only for active research work.

### 2. State the smallest literal claim

Use this form:

> Compared with **baseline B**, the paper changes **X**, intending to improve
> **Y**, under conditions **Z**.

Do not use “novel framework” or “better representation” without naming the
changed mechanism. Be explicit but brief.

### 3. Make the idea visible with a toy example

Introduce each paper-specific concept together with the smallest concrete
input. For tabular learning, use a few rows and columns; for retrieval, use a
query and two candidates; for distributed training, use two workers and one
parameter update.

Show what enters the previous method, what enters the proposed method, and what
output differs.

### 4. Reconstruct the research model

Capture:

- prediction or generation task;
- input, target, and unit of one example;
- previous strong approach;
- smallest meaningful change;
- training objective and trainable state;
- inference inputs and persistent state;
- claimed benefit and stated limitation.

Show training and inference as separate cascaded flows before describing their
differences:

```text
training_data
└─ preprocess
   └─ model_forward
      └─ loss
         └─ parameter_update

checkpoint + inference_input
└─ inference_preprocess
   └─ model_forward
      └─ prediction
```

Replace the generic frames with the paper's real components.

### 5. Reconstruct the computational model

Name all dimensions that can grow: rows, features, classes, context examples,
batch size, model width, depth, ensemble count, and retrieval corpus.

For each relevant dimension, determine:

- primary tensor dimensions;
- dominant compute operation;
- dominant resident state and temporary activation memory;
- host, device, network, and storage movement;
- runtime and memory growth;
- batching or parallelism constraints;
- reusable preprocessing, embeddings, indexes, or attention caches;
- first likely resource limit.

Label analytical complexity, author measurements, code observations, and your
own estimates separately.

### 6. Audit the evidence

Check:

- strong and fairly tuned baselines;
- equivalent preprocessing and tuning budgets;
- data-split construction and leakage risk;
- repeated runs or uncertainty reporting;
- hardware and precision comparability;
- inclusion of preprocessing, ensembles, and cold-start work;
- dataset exclusions and supported size range;
- match between benchmark data and the intended production data.

Separate three kinds of statements:

- **Paper reports:** directly supported by the source.
- **Code shows:** directly supported by implementation.
- **Engineering inference:** a reasoned conclusion that still needs measurement.

### 7. Translate to infrastructure

Describe:

- offline training and per-dataset adaptation;
- checkpoint, optimizer, preprocessing, index, and cache state;
- cold start, warm request flow, batching, and concurrency;
- compute, memory, storage, and communication requirements;
- deployment updates, rollback, observability, and fallback behavior;
- a profiling plan that can disprove the main bottleneck hypothesis.

End with at least three questions for the researchers:

1. one model-assumption question;
2. one benchmark-validity question;
3. one production-scaling question.

### 8. Stop at the selected level

Do not spend time on a proof unless it changes the user's understanding of the
objective, scaling, correctness, or research claim. Name deferred derivations,
appendices, and implementation details explicitly.

For standard and systems briefs, read and fill
[references/paper-brief-template.md](references/paper-brief-template.md). For
quick triage, return only the decision, literal claim, evidence, relevance, and
recommended next action.

## Quality check

Before returning the brief, confirm:

- The first paragraph describes the problem and claim without code identifiers.
- Every unusual concept has a toy example beside its introduction.
- Training and inference are visibly separate.
- Results, source-code observations, and engineering estimates are not mixed.
- The conclusion states where the method should work, where it may fail, and
  what to measure next.
- The output answers the user's decision instead of summarizing every section.
