# Runtime-configuration contract

The installed mutable configuration lives at
`$AGENT_HARNESS_HOME/config.json`. At the start of a goal, the coordinator reads
it and resolves only the configuration required by the selected workflow. For
an execution or review goal, it batches unresolved required choices into one
request to Lei before spawning a child. Only the coordinator may ask Lei
configuration questions or write this file.

The configuration resolves:

- the default execution root, or that every large goal asks for a location;
- the learner-state root and any external-memory mirror;
- the learner-profile update policy: `ask`, `auto`, or `off`, defaulting to
  `ask` when absent from an older installation;
- available independent-review backends, each with a stable id and model
  foundation, plus an optional supporting scanner;
- the PR-maintenance polling interval.

`configured: false` means the initial conversation has not happened. A null
value is valid after confirmation and means no global default or backend was
chosen. The coordinator records confirmed choices, then passes only the
relevant resolved values to children in their context packets. A child reports
a missing prerequisite or proposed configuration change to the coordinator; it
never asks Lei directly and never edits global configuration.

Education mode is the deliberate exception to full first-run configuration. It
may immediately use the portable learner-state fallback and leave
`configured: false`; unresolved execution roots, review backends, supporting
scanners, and PR settings do not block or prompt during that lesson. Ask about
an external-memory backend only when Lei explicitly requires it for the current
lesson.
