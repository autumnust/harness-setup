#!/usr/bin/env bash
# Run the harness installer and CLI discovery checks inside a fail-closed
# macOS Seatbelt sandbox. Offline mode is deterministic and credential-free.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="offline"
ONLINE_PROVIDER=""
INTERNAL=0
SANDBOX_ROOT=""

usage() {
  cat <<'EOF'
Usage:
  scripts/smoke-test-deployment.sh
  scripts/smoke-test-deployment.sh --offline
  scripts/smoke-test-deployment.sh --online claude|codex|all

Offline mode installs into a temporary home under a macOS Seatbelt sandbox,
denies network and all writes outside that temporary root, launches both CLI
diagnostics, validates the deployment, and removes the root on every exit.

Online mode runs the same checks, then makes a structured runtime-awareness
probe. It requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or both according to the
selected provider. Existing login files and Keychain credentials are not used.
EOF
}

while (($#)); do
  case "$1" in
    --offline)
      MODE="offline"; shift ;;
    --online)
      [[ $# -ge 2 ]] || { echo "error: --online requires claude, codex, or all" >&2; exit 2; }
      MODE="online"; ONLINE_PROVIDER="$2"; shift 2 ;;
    --internal-run)
      [[ $# -ge 3 ]] || { echo "error: invalid internal invocation" >&2; exit 2; }
      INTERNAL=1; SANDBOX_ROOT="$2"; MODE="$3"; ONLINE_PROVIDER="${4:-}"; shift "$#" ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$MODE" == "online" && ! "$ONLINE_PROVIDER" =~ ^(claude|codex|all)$ ]]; then
  echo "error: online provider must be claude, codex, or all" >&2
  exit 2
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: required command not found: $1" >&2
    exit 1
  }
}

cleanup_root() {
  local root="${1:-}"
  [[ -n "$root" && -f "$root/.harness-smoke-root" ]] || return 0
  chmod -R u+w "$root" 2>/dev/null || true
  rm -rf -- "$root"
}

cleanup_on_exit() {
  local status=$?
  trap - EXIT
  cleanup_root "$SANDBOX_ROOT"
  exit "$status"
}

run_inside_sandbox() {
  local root="$1" real_home_probe="$2" repo_probe="$3"
  local fake_home="$root/home"

  [[ "${HARNESS_SMOKE_SANDBOX_ACTIVE:-}" == "1" ]] || {
    echo "error: internal test is not running under the expected sandbox" >&2
    return 1
  }

  umask 077
  mkdir -p \
    "$fake_home/.codex" \
    "$fake_home/Documents/kumo-skills-catalog/.git" \
    "$fake_home/.cache" \
    "$fake_home/.config" \
    "$fake_home/.local/state" \
    "$root/tmp" \
    "$root/workspace"

  printf 'sandbox write allowed\n' > "$root/write-probe"
  if printf 'forbidden\n' > "$real_home_probe" 2>/dev/null; then
    echo "error: sandbox allowed a write to the real home: $real_home_probe" >&2
    return 1
  fi
  if printf 'forbidden\n' > "$repo_probe" 2>/dev/null; then
    echo "error: sandbox allowed a write to the repository: $repo_probe" >&2
    return 1
  fi
  if [[ "$MODE" == "offline" ]]; then
    if curl --silent --show-error --max-time 3 https://example.com >/dev/null 2>&1; then
      echo "error: sandbox allowed network access in offline mode" >&2
      return 1
    fi
    unset ANTHROPIC_API_KEY OPENAI_API_KEY
  fi

  export HOME="$fake_home"
  export TMPDIR="$root/tmp"
  export CODEX_HOME="$fake_home/.codex"
  export CODEX_CONFIG_DIR="$fake_home/.codex"
  export CLAUDE_CONFIG_DIR="$fake_home/.claude"
  export AGENT_HARNESS_HOME="$fake_home/.agent-harness"
  export AGENT_SKILLS_DIR="$fake_home/.agents/skills"
  export XDG_CACHE_HOME="$fake_home/.cache"
  export XDG_CONFIG_HOME="$fake_home/.config"
  export XDG_STATE_HOME="$fake_home/.local/state"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GNUPGHOME="$fake_home/.gnupg"
  export DISABLE_AUTOUPDATER=1
  export DISABLE_UPDATES=1
  export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
  export CLAUDE_CODE_DISABLE_TELEMETRY=1
  export OTEL_SDK_DISABLED=true
  unset SSH_AUTH_SOCK

  printf '%s\n' \
    'smoke_sentinel = "preserved"' \
    '' \
    '[mcp_servers.linear]' \
    'url = "https://mcp.linear.app/mcp"' \
    'enabled = true' \
    '' \
    '[mcp_servers.maas_jira]' \
    'url = "https://maas.example/maas/jira/mcp"' \
    'enabled = true' \
    > "$CODEX_HOME/config.toml"
  mkdir -p "$CLAUDE_CONFIG_DIR"
  printf '%s\n' \
    '{"enabledPlugins":{"smoke-only@example":false},"env":{"SMOKE_HOST_ONLY":"preserved","CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS":"1"}}' \
    > "$CLAUDE_CONFIG_DIR/settings.json"
  "$REPO_ROOT/install.sh" --overwrite --instance example-workstation > "$root/install.log"

  [[ -f "$AGENT_HARNESS_HOME/config.json" ]] || {
    echo "error: installer did not initialize runtime configuration" >&2
    return 1
  }
  printf '%s\n' \
    '{' \
    '  "version": 1,' \
    '  "configured": true,' \
    '  "execution_root": null,' \
    '  "learner_state_root": "$AGENT_HARNESS_HOME/state/learner-profiles",' \
    '  "learner_profile_update_policy": "ask",' \
    '  "review_backends": [' \
    '    {"id": "claude", "foundation": "anthropic"},' \
    '    {"id": "codex", "foundation": "openai"}' \
    '  ],' \
    '  "supporting_review_backend": null,' \
    '  "external_memory_backend": null,' \
    '  "review_independence": "different-foundation",' \
    '  "pr_maintenance": {"poll_interval_seconds": 600}' \
    '}' \
    > "$AGENT_HARNESS_HOME/config.json"
  printf '%s\n' '# Smoke learner profile' 'must survive update' \
    > "$AGENT_HARNESS_HOME/state/learner-profiles/smoke.md"
  mkdir -p "$CLAUDE_CONFIG_DIR/agents/lei-harness" "$CODEX_HOME/agents"
  printf '%s\n' 'retired educator fixture' \
    > "$CLAUDE_CONFIG_DIR/agents/lei-harness/educator.md"
  printf '%s\n' 'name = "educator"' \
    > "$CODEX_HOME/agents/lei-harness-educator.toml"
  "$REPO_ROOT/install.sh" --update > "$root/stale-update.log"
  "$REPO_ROOT/install.sh" --update > "$root/update.log"

  mkdir -p "$root/fake-codex-plugin/scripts"
  printf '%s\n' '// smoke plugin runtime' \
    > "$root/fake-codex-plugin/scripts/codex-companion.mjs"
  python3 \
    "$AGENT_SKILLS_DIR/cross-provider-review/scripts/invoke_review.py" \
    --caller codex --scope branch --base main --repo "$root/workspace" \
    --context 'Smoke review context: inspect the complete branch diff.' \
    --dry-run > "$root/codex-review-route.json"
  HARNESS_CODEX_PLUGIN_ROOT="$root/fake-codex-plugin" python3 \
    "$AGENT_SKILLS_DIR/cross-provider-review/scripts/invoke_review.py" \
    --caller claude --scope branch --base main --repo "$root/workspace" \
    --context 'Smoke review context: inspect the complete branch diff.' \
    --dry-run > "$root/claude-review-route.json"

  active_release="$("$AGENT_HARNESS_HOME/bin/harness-release" current)"
  "$AGENT_HARNESS_HOME/bin/harness-release" rollback "$active_release" \
    > "$root/rollback.log"

  python3 "$REPO_ROOT/tests/deployment-smoke/verify-smoke.py" install \
    --repo "$REPO_ROOT" \
    --home "$fake_home" \
    --update-log "$root/update.log"

  claude --version > "$root/claude-version.log"
  codex --version > "$root/codex-version.log"

  set +e
  claude doctor > "$root/claude-doctor.log" 2>&1
  local claude_status=$?
  codex --strict-config doctor --json > "$root/codex-doctor.json" 2> "$root/codex-doctor.err"
  local codex_status=$?
  set -e

  python3 "$REPO_ROOT/tests/deployment-smoke/verify-smoke.py" doctors \
    --claude-status "$claude_status" \
    --claude-log "$root/claude-doctor.log" \
    --codex-status "$codex_status" \
    --codex-report "$root/codex-doctor.json"

  if [[ "$MODE" == "online" ]]; then
    run_online_awareness "$root" "$fake_home"
  fi

  printf 'PASS: deployment smoke test (%s%s)\n' \
    "$MODE" "${ONLINE_PROVIDER:+, $ONLINE_PROVIDER}"
}

run_online_awareness() {
  local root="$1" fake_home="$2"
  local schema="$REPO_ROOT/tests/deployment-smoke/awareness.schema.json"
  local prompt

  case "$ONLINE_PROVIDER" in
    claude)
      [[ -n "${ANTHROPIC_API_KEY:-}" ]] || {
        echo "error: --online claude requires ANTHROPIC_API_KEY" >&2; return 1;
      } ;;
    codex)
      [[ -n "${OPENAI_API_KEY:-}" ]] || {
        echo "error: --online codex requires OPENAI_API_KEY" >&2; return 1;
      } ;;
    all)
      [[ -n "${ANTHROPIC_API_KEY:-}" && -n "${OPENAI_API_KEY:-}" ]] || {
        echo "error: --online all requires ANTHROPIC_API_KEY and OPENAI_API_KEY" >&2; return 1;
      } ;;
  esac

  python3 "$REPO_ROOT/tests/deployment-smoke/awareness-probe.py" prepare \
    --home "$fake_home" --output "$root/markers.json"

  prompt='Perform a deployment-awareness probe. Do not infer or fabricate marker values. Report the global and reviewer markers already present in your loaded instructions. Read the installed topology, workflows, runtime configuration, contracts, and execution-notes skill to obtain their markers and policy. Return the complete available role list; max depth; whether every operational child is a leaf; whether education is a coordinator mode requiring explicit entry; whether it uses the coordinator model, can delegate bounded supporting work, and defaults to no execution artifacts; whether learner-profile access is scoped to education mode; the configured learner-profile update policy; the sole canonical-state writer; review-independence rule; PR-maintainer polling interval and registered-executor messaging permission; and the learner-profile state path. Return only the requested structured result.'

  if [[ "$ONLINE_PROVIDER" == "claude" || "$ONLINE_PROVIDER" == "all" ]]; then
    local schema_json
    schema_json="$(tr -d '\n' < "$schema")"
    claude -p "$prompt Set provider to claude." \
      --agent reviewer \
      --permission-mode plan \
      --tools Read,Glob,Grep \
      --add-dir "$fake_home" \
      --setting-sources user \
      --no-session-persistence \
      --max-budget-usd "${HARNESS_CLAUDE_MAX_BUDGET_USD:-0.50}" \
      --output-format json \
      --json-schema "$schema_json" \
      > "$root/claude-awareness.json"
    python3 "$REPO_ROOT/tests/deployment-smoke/awareness-probe.py" verify \
      --provider claude --home "$fake_home" \
      --markers "$root/markers.json" --response "$root/claude-awareness.json"
  fi

  if [[ "$ONLINE_PROVIDER" == "codex" || "$ONLINE_PROVIDER" == "all" ]]; then
    git -C "$root/workspace" init -q
    codex exec \
      --ephemeral \
      --strict-config \
      --sandbox read-only \
      --cd "$root/workspace" \
      --output-schema "$schema" \
      --output-last-message "$root/codex-awareness.json" \
      --json \
      "$prompt Use the reviewer custom agent for this task. Set provider to codex." \
      > "$root/codex-events.jsonl"
    python3 "$REPO_ROOT/tests/deployment-smoke/awareness-probe.py" verify \
      --provider codex --home "$fake_home" \
      --markers "$root/markers.json" --response "$root/codex-awareness.json"
  fi
}

if (( INTERNAL )); then
  run_inside_sandbox \
    "$SANDBOX_ROOT" \
    "${HARNESS_SMOKE_HOME_PROBE:?}" \
    "${HARNESS_SMOKE_REPO_PROBE:?}"
  exit $?
fi

[[ "$(uname -s)" == "Darwin" ]] || {
  echo "error: this smoke test currently requires macOS Seatbelt" >&2
  exit 1
}
require_command sandbox-exec
require_command python3
require_command curl
require_command claude
require_command codex

if [[ "$MODE" == "online" ]]; then
  case "$ONLINE_PROVIDER" in
    claude) [[ -n "${ANTHROPIC_API_KEY:-}" ]] || { echo "error: ANTHROPIC_API_KEY is not set" >&2; exit 1; } ;;
    codex) [[ -n "${OPENAI_API_KEY:-}" ]] || { echo "error: OPENAI_API_KEY is not set" >&2; exit 1; } ;;
    all) [[ -n "${ANTHROPIC_API_KEY:-}" && -n "${OPENAI_API_KEY:-}" ]] || { echo "error: both provider API keys are required" >&2; exit 1; } ;;
  esac
fi

REAL_HOME="$HOME"
RAW_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/harness-deployment-smoke.XXXXXX")"
SANDBOX_ROOT="$(cd "$RAW_ROOT" && pwd -P)"
touch "$SANDBOX_ROOT/.harness-smoke-root"
TOKEN="$(basename "$SANDBOX_ROOT")-$$"
HOME_PROBE="$REAL_HOME/.harness-smoke-write-probe-$TOKEN"
REPO_PROBE="$REPO_ROOT/.harness-smoke-write-probe-$TOKEN"
PROFILE="$SANDBOX_ROOT/sandbox.sb"

trap cleanup_on_exit EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

printf '%s\n' \
  '(version 1)' \
  '(allow default)' \
  '(deny file-write*' \
  '  (require-all' \
  '    (require-not (subpath (param "SANDBOX_ROOT")))' \
  '    (require-not (literal "/dev/null"))))' \
  '(deny mach-lookup (global-name "com.apple.securityd"))' \
  '(deny mach-lookup (global-name "com.apple.securityd.xpc"))' \
  '(deny mach-lookup (global-name "com.apple.securityd.system"))' \
  '(deny mach-lookup (global-name "com.apple.security.agent"))' \
  '(deny mach-lookup (global-name "com.apple.trustd"))' \
  '(deny mach-lookup (global-name "com.apple.trustd.agent"))' \
  '(deny mach-lookup (global-name "com.apple.trustd.system"))' \
  '(deny mach-lookup (global-name "com.apple.accountsd"))' \
  > "$PROFILE"
if [[ "$MODE" == "offline" ]]; then
  printf '%s\n' '(deny network*)' >> "$PROFILE"
fi

set +e
HARNESS_SMOKE_SANDBOX_ACTIVE=1 \
HARNESS_SMOKE_HOME_PROBE="$HOME_PROBE" \
HARNESS_SMOKE_REPO_PROBE="$REPO_PROBE" \
sandbox-exec -D "SANDBOX_ROOT=$SANDBOX_ROOT" -f "$PROFILE" \
  /usr/bin/env bash "$0" --internal-run "$SANDBOX_ROOT" "$MODE" "$ONLINE_PROVIDER" \
  2> "$SANDBOX_ROOT/sandbox.err"
STATUS=$?
set -e

if [[ -e "$HOME_PROBE" || -e "$REPO_PROBE" ]]; then
  echo "error: an outside write probe exists after the sandbox run" >&2
  exit 1
fi
if (( STATUS != 0 )); then
  cat "$SANDBOX_ROOT/sandbox.err" >&2
  if grep -q 'sandbox_apply: Operation not permitted' "$SANDBOX_ROOT/sandbox.err"; then
    echo "error: macOS refused nested Seatbelt; run this command from a normal terminal" >&2
  fi
  exit "$STATUS"
fi
