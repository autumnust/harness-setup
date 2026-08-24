# Runtime-configuration contract

The installed mutable configuration lives at
`$AGENT_HARNESS_HOME/config.json`. At the start of a goal, the coordinator reads
it and resolves only the configuration required by the selected workflow. For
an execution or review goal, it batches unresolved required choices into one
request to the human user before spawning a child. Only the coordinator may ask the human user
configuration questions or write this file.

The configuration resolves:

- the default execution root, or that every large goal asks for a location;
- the optional local TSS host label used when creating task sessions;
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

Older configurations may omit `task_runtime`. When present,
`task_runtime.tss.host_alias` is the label a user enters in
`tss <host>:<session>` for this machine. It does not store an execution path or
change TSS configuration.
