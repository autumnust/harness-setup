# Education-only workflow

Use this path when Lei asks to learn, understand, discuss, walk through, or be
quizzed on a topic without asking for implementation or another operational
change. Education is a first-class goal; it does not require an executor result
or an operational role's recommendation.

1. The coordinator classifies the request as education-only before resolving
   execution, review, or PR-maintenance configuration.
2. Read the current learner profile from the configured learner-state root. If
   that setting is unresolved, use the portable
   `$AGENT_HARNESS_HOME/state/learner-profiles/` fallback without delaying the
   session for unrelated configuration questions.
3. Do not create an execution folder, `progress.html`, execution-notes files,
   environment-preparation artifacts, a PR queue, or implementation evidence.
   Do not invoke `exec-env-prepper`, `executor`, `reviewer`, or `pr-maintainer`.
4. Register one education session and invoke `educator` directly with the
   topic, learner context, relevant source material, and desired interaction
   mode.
5. Present the educator's initial turn, route Lei to the stable direct thread
   when supported, and wait under the interactive education-session contract.
6. At completion, record the session result and apply only approved,
   evidence-backed learner-state changes. Do not run execution retrospection
   unless the session itself produced meaningful teaching-process evidence.
7. If Lei requests implementation during the lesson, pause or complete the
   education session, return control to the coordinator, and reclassify the new
   request under the default workflow. The educator never becomes an executor.
