# Deployment smoke tests

These tests install the harness into an isolated temporary home, launch the
real Claude Code and Codex CLIs, and remove the temporary home afterward. They
run on macOS because containment uses the built-in Seatbelt facility through
`sandbox-exec`.

## Run locally

Install `claude`, `codex`, and Python 3.11 or newer, then run:

```bash
scripts/smoke-test-deployment.sh --offline
```

The command is fail-closed: it exits instead of running without Seatbelt. It
prints `PASS` only after the sandbox has denied real-home and checkout writes
and network access; the temporary root is cleaned on normal exit and failure.

For a manual runtime-awareness probe using fresh API requests:

```bash
ANTHROPIC_API_KEY=... scripts/smoke-test-deployment.sh --online claude
OPENAI_API_KEY=... scripts/smoke-test-deployment.sh --online codex
ANTHROPIC_API_KEY=... OPENAI_API_KEY=... \
  scripts/smoke-test-deployment.sh --online all
```

Online mode allows network access but retains the filesystem boundary. It reads
keys only from the process environment; it does not copy login files or permit
Keychain access. API calls may incur provider charges. Online probes are manual
because they are nondeterministic and require secrets.

## Behavior covered

The offline test verifies:

- Seatbelt permits writes only below a uniquely created temporary root.
- Offline mode denies network access and unsets provider API keys.
- The installer preserves an existing Codex setting while adding max depth 2.
- Both root sessions receive the provider adapter's fast coordinator model and
  medium reasoning policy.
- The installer preserves host-only Claude plugin settings while rendering.
- The installer preserves host-only Claude environment values while removing
  the retired agent-team flag previously used for direct education.
- Mutable coordinator configuration is initialized once and survives updates.
- Provider-neutral specs render as the complete Claude and Codex role sets.
- No Educator custom agent renders for either provider, and an update retires
  previously generated Educator files from provider discovery.
- The installed education workflow keeps teaching in Coordinator, requires
  explicit entry, uses the coordinator fast model policy, and allows bounded
  supporting delegation.
- Learner profiles are loaded only in education mode and considered for update
  only on exit. The default update policy is `ask`.
- Education creates no execution artifacts by default, while large experiments
  retain the normal preparation requirements.
- Each role includes its declared shared contracts.
- Skills deploy identically to Claude, portable, and Codex locations.
- `--update` is a no-op and does not replace mutable learner state.
- Both real CLIs launch; their doctor commands accept installed configuration.
- Only missing credentials and unreachable providers may fail Codex doctor in
  offline mode.

The online probe adds unpredictable markers after installation. Each CLI must
return those markers plus the declared roles, leaf topology, coordinator-owned
education policy, learner-state lifecycle, canonical-state authority,
independent-review rule, PR-monitor policy, and learner-state path in
schema-validated JSON. This distinguishes reading deployed instructions from
answering from general knowledge.

## CI

`.github/workflows/deployment-smoke.yml` runs the offline test on every pull
request, every push to `main` (including merges), and manual dispatch. The job
also rejects authority-policy drift before installing current published CLI
versions, so it detects both topology regressions and provider CLI format or
discovery changes. CI does not receive or persist provider credentials.

## Boundary

The test redirects all relevant home/config/cache variables and enforces the
write boundary at the operating-system level. A forced machine termination can
leave only the uniquely named directory under the system temporary directory;
the test never writes credentials there in offline mode. Seatbelt is a macOS
compatibility test, not a security boundary for executing untrusted repository
code.
