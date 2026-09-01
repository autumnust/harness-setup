#!/usr/bin/env bash
# Proves — with the real `claude` CLI, not a file-existence check — that a
# project's AGENTS.md content is only visible to Claude Code when a CLAUDE.md
# pointer (`@AGENTS.md`) sits next to it, and that every place this repo
# relies on that pointer (the repo root, the agent-task workspace template,
# and agent-workspace hydration) actually has one and actually works.
#
# This is a manual, online test: it makes real API calls through the `claude`
# CLI and is not part of the offline Seatbelt smoke suite. Run it after
# changing home/AGENTS.md's CLAUDE.md-pointer wiring, agent-task's or
# agent-workspace's hydration scripts, or this repo's own AGENTS.md/CLAUDE.md.
#
# Usage:
#   tests/deployment-smoke/verify-claude-md-import.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

command -v claude >/dev/null 2>&1 || {
  echo "error: claude CLI not found on PATH" >&2
  exit 1
}
command -v git >/dev/null 2>&1 || {
  echo "error: git not found on PATH" >&2
  exit 1
}

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/claude-md-import-test.XXXXXX")"
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

FAILURES=0
ask() {
  # ask DIR PROMPT — runs claude non-interactively in DIR, no tool access.
  local dir="$1" prompt="$2"
  (cd "$dir" && claude -p "$prompt" --model haiku --allowedTools "")
}

check() {
  # check NAME OUTPUT EXPECT_SUBSTRING — pass/fail one assertion.
  local name="$1" output="$2" expect="$3"
  if [[ "$output" == *"$expect"* ]]; then
    printf '  PASS: %s\n' "$name"
  else
    printf '  FAIL: %s\n      expected to contain: %s\n      got: %s\n' \
      "$name" "$expect" "$output"
    FAILURES=$((FAILURES + 1))
  fi
}

# --- 1. Mechanism proof: CLAUDE.md with @AGENTS.md vs. bare AGENTS.md ------
echo ">> Test 1: CLAUDE.md '@AGENTS.md' import is required for pickup"

WITH_IMPORT="$TMP_ROOT/with-import"
WITHOUT_IMPORT="$TMP_ROOT/without-import"
mkdir -p "$WITH_IMPORT" "$WITHOUT_IMPORT"

MARKER_WITH="MARKER-$(date +%s)-WITH-$$"
MARKER_WITHOUT="MARKER-$(date +%s)-WITHOUT-$$"

printf '# Test project instructions\nSecret marker: %s\n' "$MARKER_WITH" \
  > "$WITH_IMPORT/AGENTS.md"
printf '@AGENTS.md\n' > "$WITH_IMPORT/CLAUDE.md"

printf '# Test project instructions\nSecret marker: %s\n' "$MARKER_WITHOUT" \
  > "$WITHOUT_IMPORT/AGENTS.md"
# Deliberately no CLAUDE.md here.

PROMPT="Reply with ONLY the exact value after 'Secret marker:' from your \
project instructions/memory. If you have no such instruction loaded, reply \
exactly NO_MARKER_FOUND."

OUT_WITH="$(ask "$WITH_IMPORT" "$PROMPT")"
OUT_WITHOUT="$(ask "$WITHOUT_IMPORT" "$PROMPT")"

check "CLAUDE.md '@AGENTS.md' makes the marker visible" "$OUT_WITH" "$MARKER_WITH"
check "bare AGENTS.md with no CLAUDE.md stays invisible" "$OUT_WITHOUT" "NO_MARKER_FOUND"

# --- 2. This repo's own root CLAUDE.md -> AGENTS.md ------------------------
echo ">> Test 2: repo root CLAUDE.md picks up this repo's AGENTS.md"
OUT_ROOT="$(ask "$REPO_ROOT" \
  "In one sentence, per your project instructions, what kind of repo is this? \
Answer only from loaded project instructions.")"
check "repo root AGENTS.md content is loaded" "$OUT_ROOT" "meta-prompt harness"

# --- 3. agent-task workspace template's CLAUDE.md ---------------------------
echo ">> Test 3: hydrated agent-task workspace picks up its AGENTS.md"
TASK_DEST="$TMP_ROOT/tasks"
mkdir -p "$TASK_DEST"
TASK_DIR="$(python3 "$REPO_ROOT/agent-skills/agent-task/scripts/hydrate_task.py" \
  --name probe-task --objective "verify CLAUDE.md import" \
  --destination "$TASK_DEST")"
[[ -f "$TASK_DIR/CLAUDE.md" ]] || {
  echo "  FAIL: hydrated task workspace has no CLAUDE.md at $TASK_DIR" >&2
  FAILURES=$((FAILURES + 1))
}
OUT_TASK="$(ask "$TASK_DIR" \
  "Per your project instructions' numbered operating instructions, what is \
item 1? Quote it exactly, nothing else.")"
check "agent-task AGENTS.md content is loaded" "$OUT_TASK" "README.md"

# --- 4. agent-workspace hydration's generated CLAUDE.md --------------------
echo ">> Test 4: hydrated agent-workspace picks up its generated AGENTS.md"
BARE_REPO="$TMP_ROOT/bare-repo.git"
git init --bare -q "$BARE_REPO"
SEED="$TMP_ROOT/seed"
git clone -q "$BARE_REPO" "$SEED"
(cd "$SEED" && git commit -q --allow-empty -m "seed" && git push -q origin HEAD:main)
rm -rf "$SEED"

WORKSPACE_DEST="$TMP_ROOT/workspaces"
mkdir -p "$WORKSPACE_DEST"
WORKSPACE_DIR="$(python3 "$REPO_ROOT/agent-skills/agent-workspace/scripts/hydrate_workspace.py" \
  --name probe-workspace --destination "$WORKSPACE_DEST" \
  --repo "seed|$BARE_REPO|main")"
[[ -f "$WORKSPACE_DIR/CLAUDE.md" ]] || {
  echo "  FAIL: hydrated workspace has no CLAUDE.md at $WORKSPACE_DIR" >&2
  FAILURES=$((FAILURES + 1))
}
OUT_WORKSPACE="$(ask "$WORKSPACE_DIR" \
  "Per your project instructions, what does 'start-task <task-name>' do? \
Answer in one sentence, only from loaded project instructions.")"
check "agent-workspace AGENTS.md content is loaded" "$OUT_WORKSPACE" "execution folder"

echo
if ((FAILURES > 0)); then
  echo "FAIL: $FAILURES check(s) failed."
  exit 1
fi
echo "PASS: all CLAUDE.md -> AGENTS.md import checks passed."
