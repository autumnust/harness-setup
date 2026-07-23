# Review-independence contract

Review requires two judgments: Reviewer uses the same model as Executor at the
highest configured effort, while the delegated opinion uses a different model
foundation. The executor result therefore includes its provider, foundation,
concrete model, and agent identity. The coordinator includes that provenance
in the review context packet, then spawns Reviewer. Only Reviewer may invoke
the configured cross-provider review backend.

Routing is provider-specific:

- A Reviewer running under Codex invokes Claude Code with the current `opus`
  alias and `max` effort.
- A Reviewer running under Claude Code invokes the installed OpenAI Codex
  plugin's native review runtime.

Using a different model name from the executor's foundation is not sufficient
for the delegated opinion. If the cross-provider backend is unavailable,
Reviewer returns a blocked result. The coordinator and other children must not
invoke a replacement backend. Reviewer reports its own provenance and the
delegated opinion's provenance so the coordinator can verify both judgments.
