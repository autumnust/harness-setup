# Runtime-configuration contract

The installed mutable configuration lives at
`$AGENT_HARNESS_HOME/config.json`. At the start of a goal, the coordinator reads
it and resolves only the configuration required by the selected workflow. For
an execution or review goal, it batches unresolved required choices into one
request to the human user before spawning a child. Only the coordinator may ask the human user
configuration questions or write this file.

The configuration resolves:

- the default execution root, or that every large goal asks for a location;
- the local task-catalog scan roots; the execution root is also included when
  it is configured;
- the learner-state root and any external-memory mirror;
- the learner-profile update policy: `ask`, `auto`, or `off`, defaulting to
  `ask` when absent from an older installation;
- declared review-provider availability, each with a stable id and model
  foundation, plus an optional supporting scanner. The provider adapter fixes
  the cross-provider opinion route; this list does not let the coordinator
  select a different route;
- the PR-maintenance polling interval.

`configured: false` means the initial conversation has not happened. A null
value is valid after confirmation and means no global default or backend was
chosen. The coordinator records confirmed choices, then passes only the
relevant resolved values to children in their context packets. A child reports
a missing prerequisite or proposed configuration change to the coordinator; it
never asks the human user directly and never edits global configuration.

Validation accepts the retired TSS-default field in older installed files so
upgrades do not fail, but current workflows ignore it. TSS runtime targets are
explicit inputs to `tss start` and do not belong in harness configuration.

Older configurations may also omit `task_catalog`. Its default scan root is
`~/Documents`. A non-null `execution_root` is added to the effective roots, and
duplicate resolved paths are scanned once. The SQLite catalog lives at
`$AGENT_HARNESS_HOME/state/task-catalog/catalog.sqlite3`; it stores local paths
and observations and is never copied through Git.
