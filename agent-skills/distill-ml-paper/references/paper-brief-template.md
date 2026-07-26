# ML paper brief template

Use this template for standard and systems briefs. Omit sections that do not
affect the user's decision. Keep a standard brief concise; keep a systems brief
within two rendered pages unless the user requests more. Ideally, as brief as
possible.

## Decision

- **User's decision:**
- **Reading mode:**
- **Engagement level:**
- **Recommendation:** adopt, experiment, monitor, or skip
- **Reason:**

## Central idea

> Compared with **baseline B**, the paper changes **X**, intending to improve
> **Y**, under conditions **Z**.

### Smallest example

Show the minimum concrete input, previous output, and proposed output.

## Research model

- **Task and one-example unit:**
- **Input and target:**
- **Previous approach:**
- **Changed mechanism:**
- **Training objective:**
- **Trainable and persistent state:**
- **Main result:**
- **Stated limitation:**

### Training flow

```text
Replace with the paper-specific cascaded flow.
```

### Inference flow

```text
Replace with the paper-specific cascaded flow.
```

## Evidence judgment

| Question | Finding | Evidence |
|---|---|---|
| Are baselines strong and fairly tuned? | | |
| Is the split realistic and free of leakage? | | |
| Are uncertainty and repeated runs reported? | | |
| Are hardware and budgets comparable? | | |
| Are all execution costs included? | | |
| Does the benchmark resemble intended use? | | |

Distinguish “paper reports,” “code shows,” and “engineering inference.”

## Systems model

| Concern | Finding |
|---|---|
| Primary tensor dimensions | |
| Dimensions that grow | |
| Dominant compute | |
| Resident and temporary memory | |
| Data movement | |
| Dataset-specific state | |
| Batching and parallelism | |
| Cache or index reuse | |
| First likely resource limit | |

### Scaling model

For each relevant axis—rows, features, classes, context, batch, width, depth,
ensemble count, or retrieval corpus—state runtime growth, memory growth, and
the expected failure point.

## Production judgment

- **Offline training cost:**
- **Per-dataset adaptation:**
- **Cold-start path:**
- **Warm request path:**
- **Persistent state and versioning:**
- **Batching and concurrency:**
- **Autoscaling signal:**
- **Required telemetry:**
- **Fallback behavior:**

## Profiling plan

State one bottleneck hypothesis, the variables to sweep, measurements to
capture, controls to hold fixed, and the observation that would disprove it.

## Questions for researchers

1. **Model assumption:**
2. **Benchmark validity:**
3. **Production scaling:**

## Deferred

List proofs, appendices, variants, or code paths not required for this decision.
