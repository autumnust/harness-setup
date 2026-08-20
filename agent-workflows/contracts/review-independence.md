# Review-independence contract

Review is one opinion from a different model foundation. Reviewer invokes
that backend and does not add a same-foundation pass. Only Reviewer may
invoke the configured cross-provider review backend.

The provider adapter, rather than runtime configuration, chooses the
cross-provider backend. Runtime configuration may select only an optional
supporting scanner; that scanner never replaces the other-foundation opinion.
Routing is provider-specific:

- A Reviewer running under Codex invokes Claude Code with the current `opus`
  alias and `max` effort.
- A Reviewer running under Claude Code invokes the installed OpenAI Codex
  plugin's read-only adversarial-review runtime.

Using a different model name from the executor's foundation is not sufficient
for the delegated opinion. If the cross-provider backend is unavailable,
Reviewer returns a blocked result. The coordinator and other children must not
invoke a replacement backend. Reviewer reports the opinion's provenance so
the coordinator can verify the foundation.
