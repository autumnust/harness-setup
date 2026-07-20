# Review-independence contract

The primary reviewer must use a different model foundation from the executor.
The executor result therefore includes its provider, foundation, concrete
model, and agent identity. The coordinator selects a configured review backend
whose foundation differs, and includes both the executor provenance and the
independence requirement in the review context packet.

Using a different model name from the same foundation is not sufficient. If no
independent backend is configured or reachable, the coordinator reports the
review as blocked and asks Lei how to proceed; it must not silently substitute a
same-foundation reviewer. The reviewer reports its actual provenance so the
coordinator can verify the constraint.
