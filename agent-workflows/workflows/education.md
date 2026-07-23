# Coordinator education mode

Education mode is an interactive coordinator lifecycle, not a separate agent.
Enter it only when the human user explicitly asks to enter education mode, be taught, or be
quizzed on a sustained topic. A single ordinary question stays in the current
workflow. After a series of connected questions, the coordinator may suggest
education mode but must wait for the human user to accept before entering it.

## Entry

1. Identify the topic and learning objective. Do not resolve unrelated
   execution, review, or PR-maintenance configuration.
2. Read only the relevant learner profile from the configured learner-state
   root. If that setting is unresolved, use
   `$AGENT_HARNESS_HOME/state/learner-profiles/` without delaying the lesson.
   Outside education mode, do not load learner profiles unless the human user explicitly
   asks to read or update one.
3. Use the coordinator's existing fast model policy. Do not require a
   provider-specific model or fast-service toggle when the mode starts.

## Interactive loop

1. The coordinator teaches the human user directly and follows the global communication
   and explanation rules. Use the `quiz` skill for explicit quiz requests.
2. Track demonstrated understanding in the current conversation. Agreement,
   silence, or receiving an explanation is not evidence of understanding.
3. By default, create no execution folder, `progress.html`, execution-notes
   files, environment-preparation artifacts, review work, or PR queue.
4. When concrete material would improve the lesson, the coordinator may resume
   a relevant existing child or spawn a new child for a bounded task such as
   collecting data, running an experiment, inspecting a prior implementation,
   or producing a visualization script. Children return evidence or artifacts
   to the coordinator and never take over the teaching conversation.
5. Supporting work that is small remains artifact-light. Large, remote,
   hardware-dependent, or multi-session experiments follow the normal
   execution-preparation rules, including user confirmation and the configured
   execution folder.

## Exit

1. Exit when the human user explicitly finishes or pauses education mode, or confirms a
   transition to another workflow. A request for product implementation exits
   education mode; producing a bounded teaching artifact does not.
2. Decide whether the conversation contains durable evidence for a learner
   profile change. When it does, prepare a concise replacement-snapshot proposal
   under the learning-state contract. When it does not, make no proposal.
3. Apply the configured learner-profile update policy: `ask` requires the human user's
   approval, `auto` applies well-supported changes, and `off` discards the
   proposal. A missing policy means `ask`.
4. Discard temporary learning observations after exit. Invoke retrospector only
   when the lesson produced meaningful evidence about the teaching process.
