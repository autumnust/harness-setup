# Runtime-configuration contract

The installed mutable configuration lives at
`$AGENT_HARNESS_HOME/config.json`. At the start of a goal, before spawning a
child, the coordinator reads it and batches unresolved choices into one request
to Lei. Only the coordinator may ask Lei configuration questions or write this
file.

The configuration resolves:

- the default execution root, or that every large goal asks for a location;
- the learner-state root and any external-memory mirror;
- available independent-review backends, each with a stable id and model
  foundation, plus an optional supporting scanner;
- the PR-maintenance polling interval.

`configured: false` means the initial conversation has not happened. A null
value is valid after confirmation and means no global default or backend was
chosen. The coordinator records confirmed choices, then passes only the
relevant resolved values to children in their context packets. A child reports
a missing prerequisite or proposed configuration change to the coordinator; it
never asks Lei directly and never edits global configuration.
