#!/usr/bin/env bash
# Installs the global coding-agent harness onto this machine
# (tool-agnostic ~/AGENTS.md + native Claude/Codex integration: settings,
# skills, custom agents, and workflow specifications).
#
# Usage:
#   ./install.sh                  # Refuses to clobber any existing global
#                                 # config. If conflicts are found, lists
#                                 # them and exits non-zero so Claude Code
#                                 # (or you) can decide per-file.
#   ./install.sh --backup         # Move existing conflicting files to
#                                 # <path>.bak.<timestamp> and proceed.
#   ./install.sh --overwrite      # Replace existing files with no backup.
#   ./install.sh --skip-existing  # Keep every existing file, only install
#                                 # what is missing.
#   ./install.sh --update         # Steady-state sync after the repo changes:
#                                 # only rewrites files that actually differ,
#                                 # shows a diff and backs up each before
#                                 # writing, and is a no-op when in sync.
#                                 # (See update.sh, which git-pulls first.)
#   ./install.sh --instance NAME  # Append instances/NAME.md to the deployed
#                                 # ~/AGENTS.md and remember the selection.
#   ./install.sh --with-tss       # Optionally install the lockfile-pinned TSS
#                                 # client into ~/bin/tss.
set -euo pipefail

MODE="prompt"
PRESERVE_RELEASE=1
INSTANCE_PROFILE=""
INSTANCE_SELECTION="remembered"
WITH_TSS=0
while (($#)); do
  case "$1" in
    --backup)         MODE="backup"; shift ;;
    --overwrite)      MODE="overwrite"; shift ;;
    --skip-existing)  MODE="skip"; shift ;;
    --update)         MODE="update"; shift ;;
    --no-release)     PRESERVE_RELEASE=0; shift ;;
    --instance)
      [[ $# -ge 2 ]] || {
        echo "Missing profile name after --instance" >&2
        exit 2
      }
      INSTANCE_PROFILE="$2"
      INSTANCE_SELECTION="set"
      shift 2
      ;;
    --no-instance)
      INSTANCE_PROFILE=""
      INSTANCE_SELECTION="clear"
      shift
      ;;
    --with-tss)       WITH_TSS=1; shift ;;
    -h|--help)
      cat <<'HELP'
Installs the global coding-agent harness onto this machine
(tool-agnostic core + native Claude Code and Codex integration).

Usage:
  ./install.sh                  Refuses to clobber any existing global
                                config. If conflicts are found, lists
                                them and exits non-zero so Claude Code
                                (or you) can decide per-file.
  ./install.sh --backup         Move existing conflicting files to
                                <path>.bak.<timestamp> and proceed.
  ./install.sh --overwrite      Replace existing files with no backup.
  ./install.sh --skip-existing  Keep every existing file, only install
                                what is missing.
  ./install.sh --update         Steady-state sync after the repo changes:
                                rewrite only files that differ, showing a
                                diff and backing up each first; no-op when
                                already in sync. update.sh wraps this and
                                git-pulls beforehand.
  ./install.sh --instance NAME  Append instances/NAME.md to ~/AGENTS.md and
                                remember NAME for later updates and rollback.
  ./install.sh --no-instance    Deploy only the portable instructions and
                                clear any remembered instance profile.
  ./install.sh --with-tss       Also fetch the lockfile-pinned TSS client,
                                store its source under
                                ~/.agent-harness/dependencies/tss, and install
                                its tss command into ~/bin/tss.
HELP
      exit 0 ;;
    *)
      echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_CONFIG_DIR:-$HOME/.codex}"
AGENT_HARNESS_HOME="${AGENT_HARNESS_HOME:-$HOME/.agent-harness}"
PORTABLE_SKILLS_DIR="${AGENT_SKILLS_DIR:-$HOME/.agents/skills}"
INSTANCE_PROFILE_STATE="$AGENT_HARNESS_HOME/instance-profile"

if [[ "$INSTANCE_SELECTION" == "remembered" && -f "$INSTANCE_PROFILE_STATE" ]]; then
  INSTANCE_PROFILE="$(<"$INSTANCE_PROFILE_STATE")"
fi
if [[ -n "$INSTANCE_PROFILE" ]]; then
  if [[ ! "$INSTANCE_PROFILE" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "Invalid instance profile name: $INSTANCE_PROFILE" >&2
    exit 2
  fi
  INSTANCE_PROFILE_SOURCE="$REPO_ROOT/instances/$INSTANCE_PROFILE.md"
  if [[ ! -f "$INSTANCE_PROFILE_SOURCE" ]]; then
    LOCAL_PROFILE_SOURCE="$REPO_ROOT/instances/$INSTANCE_PROFILE.local.md"
    if [[ -f "$LOCAL_PROFILE_SOURCE" ]]; then
      echo "Using local instance profile: $INSTANCE_PROFILE.local"
      INSTANCE_PROFILE="$INSTANCE_PROFILE.local"
      INSTANCE_PROFILE_SOURCE="$LOCAL_PROFILE_SOURCE"
      INSTANCE_SELECTION="set"
    else
      echo "Unknown instance profile: $INSTANCE_PROFILE" >&2
      echo "Expected file: $INSTANCE_PROFILE_SOURCE" >&2
      echo "Local alternative: $LOCAL_PROFILE_SOURCE" >&2
      exit 2
    fi
  fi
fi

# A selected profile may also provide private skills beside its instruction
# paragraph.  These directories are intentionally local: for example,
# instances/nvda-laptop.local/agent-skills/ is available only on that laptop.
# They install in addition to the portable agent-skills/ tree.
INSTANCE_SKILLS_DIR=""
if [[ -n "$INSTANCE_PROFILE" ]]; then
  candidate_instance_skills="$REPO_ROOT/instances/$INSTANCE_PROFILE/agent-skills"
  if [[ -d "$candidate_instance_skills" ]]; then
    INSTANCE_SKILLS_DIR="$candidate_instance_skills"
  fi
fi

# A config directory or installed binary signals that this machine uses Codex;
# no separate opt-in flag is required, including before Codex's first launch.
CODEX_PRESENT=0
if [[ -d "$CODEX_DIR" ]] || command -v codex >/dev/null 2>&1; then
  CODEX_PRESENT=1
fi
TS="$(date +%Y%m%dT%H%M%S)"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/harness-install.XXXXXX")"
cleanup() { rm -rf "$TEMP_ROOT"; }
trap cleanup EXIT

TSS_STAGED=""
if (( WITH_TSS )); then
  TSS_STAGED="$TEMP_ROOT/tss"
  python3 "$REPO_ROOT/scripts/prepare-git-dependency.py" \
    --manifest "$REPO_ROOT/dependencies/tss.json" \
    --destination "$TSS_STAGED"
fi

RENDERED_AGENTS="$TEMP_ROOT/AGENTS.md"
cp "$REPO_ROOT/home/AGENTS.md" "$RENDERED_AGENTS"
if [[ -n "$INSTANCE_PROFILE" ]]; then
  printf '\n' >> "$RENDERED_AGENTS"
  cat "$INSTANCE_PROFILE_SOURCE" >> "$RENDERED_AGENTS"
fi

RELEASE_STAGED="$TEMP_ROOT/release"
RELEASE_ID=""
if (( PRESERVE_RELEASE )); then
  RELEASE_ID="$(python3 "$REPO_ROOT/scripts/harness-release.py" \
    --home "$AGENT_HARNESS_HOME" prepare \
    --source "$REPO_ROOT" \
    --destination "$RELEASE_STAGED")"
fi

# Validate the provider-neutral topology and render provider-native agent files
# before conflict detection, so install remains all-or-nothing on invalid specs.
python3 "$REPO_ROOT/scripts/render-agents.py" \
  --source "$REPO_ROOT/agent-workflows" \
  --out "$TEMP_ROOT/agents"

if (( CODEX_PRESENT )); then
  CODEX_COORDINATOR_MODEL="$(python3 -c \
    'import json, sys; print(json.load(open(sys.argv[1]))["models"]["coordinator"])' \
    "$REPO_ROOT/agent-workflows/adapters/codex.json")"
  CODEX_COORDINATOR_EFFORT="$(python3 -c \
    'import json, sys; print(json.load(open(sys.argv[1]))["reasoning_effort"]["medium"])' \
    "$REPO_ROOT/agent-workflows/adapters/codex.json")"
  python3 "$REPO_ROOT/scripts/render-codex-config.py" \
    --input "$CODEX_DIR/config.toml" \
    --output "$TEMP_ROOT/codex-config.toml" \
    --max-depth 2 \
    --model "$CODEX_COORDINATOR_MODEL" \
    --reasoning-effort "$CODEX_COORDINATOR_EFFORT"
fi

if [[ -f "$AGENT_HARNESS_HOME/config.json" ]]; then
  python3 "$REPO_ROOT/scripts/render-agents.py" \
    --validate-runtime-config "$AGENT_HARNESS_HOME/config.json"
fi

say()  { printf '\033[1;34m>>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }

# --- Conflict detection (runs before any writes) ----------------------------
declare -a CONFLICTS=()
record_conflict() {
  local target="$1"
  if [[ -e "$target" || -L "$target" ]]; then
    CONFLICTS+=("$target")
  fi
}
record_conflict "$HOME/AGENTS.md"
record_conflict "$CLAUDE_DIR/CLAUDE.md"
record_conflict "$CLAUDE_DIR/settings.json"
record_conflict "$AGENT_HARNESS_HOME/specs"
record_conflict "$AGENT_HARNESS_HOME/bin/harness-release"
if (( WITH_TSS )); then
  record_conflict "$AGENT_HARNESS_HOME/dependencies/tss"
  record_conflict "$HOME/bin/tss"
fi
for agent_file in "$TEMP_ROOT"/agents/claude/*; do
  record_conflict "$CLAUDE_DIR/agents/agent-harness/$(basename "$agent_file")"
done
for agent_file in "$CLAUDE_DIR"/agents/agent-harness/*.md; do
  [[ -e "$agent_file" ]] && record_conflict "$agent_file"
done
for agent_file in "$CLAUDE_DIR"/agents/lei-harness/*.md; do
  [[ -e "$agent_file" ]] && record_conflict "$agent_file"
done
if (( CODEX_PRESENT )); then
  record_conflict "$CODEX_DIR/AGENTS.md"
  record_conflict "$CODEX_DIR/config.toml"
  for agent_file in "$TEMP_ROOT"/agents/codex/*; do
    record_conflict "$CODEX_DIR/agents/$(basename "$agent_file")"
  done
  for agent_file in "$CODEX_DIR"/agents/agent-harness-*.toml; do
    [[ -e "$agent_file" ]] && record_conflict "$agent_file"
  done
  for agent_file in "$CODEX_DIR"/agents/lei-harness-*.toml; do
    [[ -e "$agent_file" ]] && record_conflict "$agent_file"
  done
fi
for skill_root in "$REPO_ROOT/agent-skills" "$INSTANCE_SKILLS_DIR"; do
  [[ -n "$skill_root" && -d "$skill_root" ]] || continue
  for skill_dir in "$skill_root"/*/; do
    [[ -d "$skill_dir" ]] || continue
    record_conflict "$CLAUDE_DIR/skills/$(basename "$skill_dir")"
    if (( CODEX_PRESENT )); then
      record_conflict "$PORTABLE_SKILLS_DIR/$(basename "$skill_dir")"
      record_conflict "$CODEX_DIR/skills/$(basename "$skill_dir")"
    fi
  done
done

if (( ${#CONFLICTS[@]} > 0 )) && [[ "$MODE" == "prompt" ]]; then
  warn "Existing global agent setup detected on this device:"
  for c in "${CONFLICTS[@]}"; do printf '    %s\n' "$c" >&2; done
  cat >&2 <<EOF

Refusing to overwrite without explicit instructions. Re-run with one of:

  ./install.sh --backup         Move each conflicting file to
                                <path>.bak.${TS} before installing.
                                (Safest — nothing is lost.)

  ./install.sh --overwrite      Replace existing files outright.
                                Use only if you are sure the current
                                machine has nothing worth keeping.

  ./install.sh --skip-existing  Keep every existing file; only install
                                what is missing.

If you are running this from inside Claude Code, ask the user which
mode to use before re-invoking.
EOF
  exit 1
fi

# Apply the chosen mode to a single target path.
handle_existing() {
  local target="$1"
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    return 0   # nothing there, proceed to install
  fi
  case "$MODE" in
    backup)
      local bak="${target}.bak.${TS}"
      say "Backing up existing $target → $bak"
      mv "$target" "$bak"
      ;;
    overwrite)
      say "Overwriting existing $target"
      rm -rf "$target"
      ;;
    skip)
      warn "Skipping $target (already exists)"
      return 1   # signal caller to skip this install
      ;;
  esac
  return 0
}

# Counters for the --update summary.
UPDATED=0
UNCHANGED=0

# place_file SRC DST — install a single rendered file at DST honoring MODE.
# In --update mode: skip when byte-identical, otherwise diff + back up + write.
place_file() {
  local src="$1" dst="$2"
  if [[ "$MODE" == "update" ]]; then
    if [[ -f "$dst" && ! -L "$dst" ]] && cmp -s "$src" "$dst"; then
      ok "in sync: $dst"; UNCHANGED=$((UNCHANGED + 1)); return 0
    fi
    if [[ -e "$dst" || -L "$dst" ]]; then
      say "Updating $dst (changed):"
      diff -u "$dst" "$src" | sed 's/^/    /' || true
      local bak="${dst}.bak.${TS}"
      mv "$dst" "$bak"; warn "backed up prior → $bak"
    fi
    cp "$src" "$dst"; ok "synced $dst"; UPDATED=$((UPDATED + 1)); return 0
  fi
  if handle_existing "$dst"; then cp "$src" "$dst"; ok "Wrote $dst"; fi
}

# place_tree SRC DST — install a directory tree at DST honoring MODE.
place_tree() {
  local src="$1" dst="$2"
  if [[ "$MODE" == "update" ]]; then
    if [[ -d "$dst" ]] && diff -rq "$src" "$dst" >/dev/null 2>&1; then
      ok "in sync: $dst"; UNCHANGED=$((UNCHANGED + 1)); return 0
    fi
    if [[ -e "$dst" || -L "$dst" ]]; then
      say "Updating $dst (changed)"
      local bak="${dst}.bak.${TS}"
      mv "$dst" "$bak"; warn "backed up prior → $bak"
    fi
    cp -R "$src" "$dst"; ok "synced $dst"; UPDATED=$((UPDATED + 1)); return 0
  fi
  if handle_existing "$dst"; then cp -R "$src" "$dst"; ok "Installed skill: $(basename "$dst")"; fi
}

# place_symlink TARGET LINK — install one stable link honoring MODE.
place_symlink() {
  local target="$1" link="$2"
  if [[ "$MODE" == "update" ]]; then
    if [[ -L "$link" && "$(readlink "$link")" == "$target" ]]; then
      ok "in sync: $link (symlink)"; UNCHANGED=$((UNCHANGED + 1)); return 0
    fi
    if [[ -e "$link" || -L "$link" ]]; then
      mv "$link" "$link.bak.${TS}"; warn "backed up prior → $link.bak.${TS}"
    fi
    ln -s "$target" "$link"; ok "synced $link (symlink)"; UPDATED=$((UPDATED + 1)); return 0
  fi
  if handle_existing "$link"; then
    ln -s "$target" "$link"; ok "Symlink in place: $link → $target"
  fi
}

# Remove a generated custom-agent file whose role no longer exists. Backups use
# a non-agent extension so providers stop discovering the retired role.
remove_stale_agent() {
  local target="$1"
  case "$MODE" in
    backup|update)
      mv "$target" "$target.bak.$TS"
      warn "retired generated agent → $target.bak.$TS"
      [[ "$MODE" == "update" ]] && UPDATED=$((UPDATED + 1))
      ;;
    overwrite)
      rm -f "$target"
      ok "Removed retired generated agent: $target"
      ;;
    skip)
      warn "Keeping retired generated agent in --skip-existing mode: $target"
      ;;
  esac
}

prune_stale_agents() {
  local installed_dir="$1" rendered_dir="$2" pattern="$3" target
  for target in "$installed_dir"/$pattern; do
    [[ -e "$target" ]] || continue
    [[ -e "$rendered_dir/$(basename "$target")" ]] && continue
    remove_stale_agent "$target"
  done
}

# --- 1. AGENTS.md + CLAUDE.md symlink ---------------------------------------
if [[ -n "$INSTANCE_PROFILE" ]]; then
  say "Installing ~/AGENTS.md (global instructions + $INSTANCE_PROFILE profile)"
else
  say "Installing ~/AGENTS.md (global instructions)"
fi
place_file "$RENDERED_AGENTS" "$HOME/AGENTS.md"

say "Ensuring $CLAUDE_DIR exists"
mkdir -p "$CLAUDE_DIR"

say "Linking $CLAUDE_DIR/CLAUDE.md → $HOME/AGENTS.md"
place_symlink "$HOME/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"

if (( CODEX_PRESENT )); then
  say "Ensuring $CODEX_DIR exists and linking its global instructions"
  mkdir -p "$CODEX_DIR"
  place_symlink "$HOME/AGENTS.md" "$CODEX_DIR/AGENTS.md"
fi

# --- 2. settings.json (with node path patched for this device) --------------
say "Installing $CLAUDE_DIR/settings.json"

# Locate a real node binary. `command -v` misses nvm-managed node over a
# non-interactive ssh session (nvm is sourced from ~/.bashrc, which such shells
# skip), so also probe nvm's install dir and the common system paths before
# giving up. Pick the newest nvm version when several are installed.
NODE_BIN="$(command -v node || true)"
if [[ -z "$NODE_BIN" && -d "$HOME/.nvm/versions/node" ]]; then
  NODE_BIN="$(ls -1d "$HOME"/.nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)"
fi
if [[ -z "$NODE_BIN" ]]; then
  for cand in /usr/local/bin/node /usr/bin/node /opt/homebrew/bin/node; do
    [[ -x "$cand" ]] && NODE_BIN="$cand" && break
  done
fi
if [[ -z "$NODE_BIN" ]]; then
  warn "node not found (PATH, nvm, or common locations) — claude-hud statusline"
  warn "will not render until node is installed. Install it, then rerun to patch."
  NODE_BIN="/opt/homebrew/bin/node"
fi
say "Pinning statusline node binary to: $NODE_BIN"

# The statusline command embeds a literal node path. Render the device-specific
# settings.json into a temp file, then place it (so --update can diff against it).
# The render is ADDITIVE for plugins: it patches the node path and forces the
# repo's baseline keys, but unions enabledPlugins / extraKnownMarketplaces with
# whatever this machine already has, so host-specific plugins are never dropped.
RENDERED_SETTINGS="$TEMP_ROOT/claude-settings.json"
python3 "$REPO_ROOT/scripts/render-claude-settings.py" \
  --source "$REPO_ROOT/claude/settings.json" \
  --output "$RENDERED_SETTINGS" \
  --node-bin "$NODE_BIN" \
  --existing "$CLAUDE_DIR/settings.json"
place_file "$RENDERED_SETTINGS" "$CLAUDE_DIR/settings.json"

# --- 3. Portable workflow specs + native custom agents ---------------------
say "Installing portable workflow specifications"
mkdir -p "$AGENT_HARNESS_HOME"
place_tree "$REPO_ROOT/agent-workflows" "$AGENT_HARNESS_HOME/specs"
mkdir -p "$AGENT_HARNESS_HOME/bin"
place_file \
  "$REPO_ROOT/scripts/harness-release.py" \
  "$AGENT_HARNESS_HOME/bin/harness-release"

# Runtime configuration is mutable, confirmed by the coordinator, and never
# managed by place_file after initialization.
if [[ ! -e "$AGENT_HARNESS_HOME/config.json" ]]; then
  cp "$REPO_ROOT/agent-workflows/runtime-config.defaults.json" \
    "$AGENT_HARNESS_HOME/config.json"
  ok "Initialized coordinator runtime configuration"
fi

say "Installing Claude custom agents"
for agent_file in "$CLAUDE_DIR"/agents/lei-harness/*.md; do
  [[ -e "$agent_file" ]] && remove_stale_agent "$agent_file"
done
mkdir -p "$CLAUDE_DIR/agents/agent-harness"
prune_stale_agents \
  "$CLAUDE_DIR/agents/agent-harness" "$TEMP_ROOT/agents/claude" '*.md'
for agent_file in "$TEMP_ROOT"/agents/claude/*; do
  place_file "$agent_file" "$CLAUDE_DIR/agents/agent-harness/$(basename "$agent_file")"
done

if (( CODEX_PRESENT )); then
  say "Installing Codex custom agents and max_depth=2"
  mkdir -p "$CODEX_DIR/agents"
  for agent_file in "$CODEX_DIR"/agents/lei-harness-*.toml; do
    [[ -e "$agent_file" ]] && remove_stale_agent "$agent_file"
  done
  prune_stale_agents "$CODEX_DIR/agents" "$TEMP_ROOT/agents/codex" \
    'agent-harness-*.toml'
  for agent_file in "$TEMP_ROOT"/agents/codex/*; do
    place_file "$agent_file" "$CODEX_DIR/agents/$(basename "$agent_file")"
  done
  place_file "$TEMP_ROOT/codex-config.toml" "$CODEX_DIR/config.toml"
fi

# Mutable learner state is initialized once and never managed by place_tree.
# Migrate the old Claude-only profile directory by copying, without deleting it.
mkdir -p "$AGENT_HARNESS_HOME/state"
# Remove the retired session-state directory only when no historical records
# remain. Mutable records are never deleted by installation.
rmdir "$AGENT_HARNESS_HOME/state/education-sessions" 2>/dev/null || true
if [[ ! -e "$AGENT_HARNESS_HOME/state/learner-profiles" ]]; then
  if [[ -d "$CLAUDE_DIR/learner-profiles" ]]; then
    cp -R "$CLAUDE_DIR/learner-profiles" "$AGENT_HARNESS_HOME/state/learner-profiles"
    ok "Copied legacy learner profiles into portable state (originals retained)"
  else
    mkdir -p "$AGENT_HARNESS_HOME/state/learner-profiles"
  fi
fi

# --- 4. Skills (portable plus selected-profile skills → every tool) --------
# agent-skills/ is the portable source of truth.  A selected instance profile
# may add private skills from instances/<profile>/agent-skills/. Claude Code
# and Codex CLI use the same on-disk convention (a directory per skill holding
# SKILL.md), so each selected skill is installed as-is into every target.
say "Installing portable skills into $CLAUDE_DIR/skills/"
mkdir -p "$CLAUDE_DIR/skills"
if (( CODEX_PRESENT )); then
  say "Codex CLI detected — installing into $PORTABLE_SKILLS_DIR/"
  say "Also retaining the legacy-compatible $CODEX_DIR/skills/ copy"
  mkdir -p "$PORTABLE_SKILLS_DIR"
  mkdir -p "$CODEX_DIR/skills"
fi
for skill_root in "$REPO_ROOT/agent-skills" "$INSTANCE_SKILLS_DIR"; do
  [[ -n "$skill_root" && -d "$skill_root" ]] || continue
  if [[ "$skill_root" == "$INSTANCE_SKILLS_DIR" ]]; then
    say "Installing skills for the selected instance profile"
  fi
  for skill_dir in "$skill_root"/*/; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    place_tree "$skill_dir" "$CLAUDE_DIR/skills/$name"
    if (( CODEX_PRESENT )); then
      place_tree "$skill_dir" "$PORTABLE_SKILLS_DIR/$name"
      place_tree "$skill_dir" "$CODEX_DIR/skills/$name"
    fi
  done
done

# --- Optional companion: TSS -----------------------------------------------
if (( WITH_TSS )); then
  say "Installing lockfile-pinned TSS companion"
  mkdir -p "$AGENT_HARNESS_HOME/dependencies" "$HOME/bin"
  place_tree "$TSS_STAGED" "$AGENT_HARNESS_HOME/dependencies/tss"
  place_file "$TSS_STAGED/tss" "$HOME/bin/tss"
  chmod u+x "$HOME/bin/tss"
fi

# This small machine-local file lets ordinary updates and rollback reuse the
# selected paragraph without requiring another command-line option.
case "$INSTANCE_SELECTION" in
  set)
    mkdir -p "$AGENT_HARNESS_HOME"
    printf '%s\n' "$INSTANCE_PROFILE" > "$TEMP_ROOT/instance-profile"
    cp "$TEMP_ROOT/instance-profile" "$INSTANCE_PROFILE_STATE"
    ok "Remembered instance profile: $INSTANCE_PROFILE"
    ;;
  clear)
    rm -f "$INSTANCE_PROFILE_STATE"
    ok "Cleared remembered instance profile"
    ;;
esac

# Register only after every managed target has been installed successfully.
if (( PRESERVE_RELEASE )); then
  REGISTERED_RELEASE="$(python3 "$REPO_ROOT/scripts/harness-release.py" \
    --home "$AGENT_HARNESS_HOME" register \
    --staged "$RELEASE_STAGED")"
  [[ "$REGISTERED_RELEASE" == "$RELEASE_ID" ]] || {
    echo "error: staged and registered release IDs differ" >&2
    exit 1
  }
  ok "Active harness release: $REGISTERED_RELEASE"
fi

# --- 5. Final report --------------------------------------------------------
if [[ "$MODE" == "update" ]]; then
  printf '\n'
  ok "Harness sync complete: $UPDATED updated, $UNCHANGED already in sync."
  printf '\n'
  if (( UPDATED > 0 )); then
    printf '%s\n' \
      "Prior contents of any changed file were saved as <path>.bak.${TS}." \
      "Restart active Claude Code or Codex sessions so they re-read updated config."
  fi
  exit 0
fi

printf '\n'
ok "Global coding-agent harness installed."
printf '\n%s\n' \
  "Next steps:" \
  "  1. Launch Claude Code in any directory. On first launch it will:" \
  "       - Read $CLAUDE_DIR/settings.json" \
  "       - See the enabled plugins and their marketplaces, including the" \
  "         OpenAI Codex plugin used by the Claude Reviewer" \
  "       - Install them automatically into $CLAUDE_DIR/plugins/cache/" \
  "  2. If a plugin does not auto-install, run inside Claude Code:" \
  "         /plugin" \
  "       and enable it from the entries listed in settings.json." \
  "  3. Verify the statusline renders. If not, check node path in" \
  "       $CLAUDE_DIR/settings.json  (statusLine.command embeds it literally)." \
  "" \
  "Files this run created or replaced (with .bak.${TS} for any prior contents):" \
  "  $HOME/AGENTS.md" \
  "  $CLAUDE_DIR/CLAUDE.md       (symlink -> $HOME/AGENTS.md)" \
  "  $CLAUDE_DIR/settings.json" \
  "  $CLAUDE_DIR/skills/*" \
  "  $CLAUDE_DIR/agents/agent-harness/*" \
  "  $AGENT_HARNESS_HOME/specs" \
  "  $AGENT_HARNESS_HOME/releases/* and current" \
  "  $AGENT_HARNESS_HOME/bin/harness-release" \
  "  $AGENT_HARNESS_HOME/config.json  (initialized once, never overwritten)" \
  "  $AGENT_HARNESS_HOME/state/learner-profiles  (initialized, never overwritten)"
if (( WITH_TSS )); then
  printf '%s\n' \
    "  $AGENT_HARNESS_HOME/dependencies/tss  (lockfile-pinned source)" \
    "  $HOME/bin/tss"
fi
if (( CODEX_PRESENT )); then
  printf '%s\n' \
    "  $CODEX_DIR/AGENTS.md        (symlink -> $HOME/AGENTS.md)" \
    "  $CODEX_DIR/config.toml      (agents.max_depth = 2)" \
    "  $CODEX_DIR/agents/agent-harness-*.toml" \
    "  $PORTABLE_SKILLS_DIR/*" \
    "  $CODEX_DIR/skills/*         (legacy-compatible copy)"
fi
printf '\n%s\n' \
  "Not migrated (intentionally - these are per-project or per-session):" \
  "  $CLAUDE_DIR/projects/   $CLAUDE_DIR/sessions/   $CLAUDE_DIR/tasks/" \
  "  $CLAUDE_DIR/plugins/cache/   $CLAUDE_DIR/history.jsonl" \
  "  Any project-local .claude/ directories (bench-ec2, gpu-ec2, ship, learn, ...)" \
  ""
