# Review-independence contract

The primary review must use a different model foundation from the executor.
The executor result therefore includes its provider, foundation, concrete
model, and agent identity. The coordinator includes that provenance in the
review context packet, then spawns the Reviewer. Only the Reviewer may invoke
the configured cross-provider review backend.

Routing is provider-specific:

- A Reviewer running under Codex invokes Claude Code with the current `opus`
  alias and `max` effort.
- A Reviewer running under Claude Code invokes the installed OpenAI Codex
  plugin's native review runtime.

Using a different model name from the executor's foundation is not sufficient.
If the cross-provider backend is unavailable, the Reviewer returns a blocked
result. The coordinator and other children must not invoke a replacement
backend. The Reviewer reports both its router provenance and the external
review provenance so the coordinator can verify the requirement.
