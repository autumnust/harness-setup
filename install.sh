#!/usr/bin/env bash
# Installs Lei's global coding-agent harness onto this machine
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
set -euo pipefail

MODE="prompt"
for arg in "$@"; do
  case "$arg" in
    --backup)         MODE="backup" ;;
    --overwrite)      MODE="overwrite" ;;
    --skip-existing)  MODE="skip" ;;
    --update)         MODE="update" ;;
    -h|--help)
      cat <<'HELP'
Installs Lei's global coding-agent harness onto this machine
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
HELP
      exit 0 ;;
    *)
      echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_CONFIG_DIR:-$HOME/.codex}"
AGENT_HARNESS_HOME="${AGENT_HARNESS_HOME:-$HOME/.agent-harness}"
PORTABLE_SKILLS_DIR="${AGENT_SKILLS_DIR:-$HOME/.agents/skills}"
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

# Validate the provider-neutral topology and render provider-native agent files
# before conflict detection, so install remains all-or-nothing on invalid specs.
python3 "$REPO_ROOT/scripts/render-agents.py" \
  --source "$REPO_ROOT/agent-workflows" \
  --out "$TEMP_ROOT/agents"

if (( CODEX_PRESENT )); then
  python3 "$REPO_ROOT/scripts/set-codex-agent-limits.py" \
    --input "$CODEX_DIR/config.toml" \
    --output "$TEMP_ROOT/codex-config.toml" \
    --max-depth 2
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
for agent_file in "$TEMP_ROOT"/agents/claude/*; do
  record_conflict "$CLAUDE_DIR/agents/lei-harness/$(basename "$agent_file")"
done
if (( CODEX_PRESENT )); then
  record_conflict "$CODEX_DIR/AGENTS.md"
  record_conflict "$CODEX_DIR/config.toml"
  for agent_file in "$TEMP_ROOT"/agents/codex/*; do
    record_conflict "$CODEX_DIR/agents/$(basename "$agent_file")"
  done
fi
for skill_dir in "$REPO_ROOT"/agent-skills/*/; do
  record_conflict "$CLAUDE_DIR/skills/$(basename "$skill_dir")"
  if (( CODEX_PRESENT )); then
    record_conflict "$PORTABLE_SKILLS_DIR/$(basename "$skill_dir")"
    record_conflict "$CODEX_DIR/skills/$(basename "$skill_dir")"
  fi
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

# --- 1. AGENTS.md + CLAUDE.md symlink ---------------------------------------
say "Installing ~/AGENTS.md (global instructions)"
place_file "$REPO_ROOT/home/AGENTS.md" "$HOME/AGENTS.md"

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

say "Installing Claude custom agents"
mkdir -p "$CLAUDE_DIR/agents/lei-harness"
for agent_file in "$TEMP_ROOT"/agents/claude/*; do
  place_file "$agent_file" "$CLAUDE_DIR/agents/lei-harness/$(basename "$agent_file")"
done

if (( CODEX_PRESENT )); then
  say "Installing Codex custom agents and max_depth=2"
  mkdir -p "$CODEX_DIR/agents"
  for agent_file in "$TEMP_ROOT"/agents/codex/*; do
    place_file "$agent_file" "$CODEX_DIR/agents/$(basename "$agent_file")"
  done
  place_file "$TEMP_ROOT/codex-config.toml" "$CODEX_DIR/config.toml"
fi

# Mutable learner state is initialized once and never managed by place_tree.
# Migrate the old Claude-only profile directory by copying, without deleting it.
mkdir -p "$AGENT_HARNESS_HOME/state"
if [[ ! -e "$AGENT_HARNESS_HOME/state/learner-profiles" ]]; then
  if [[ -d "$CLAUDE_DIR/learner-profiles" ]]; then
    cp -R "$CLAUDE_DIR/learner-profiles" "$AGENT_HARNESS_HOME/state/learner-profiles"
    ok "Copied legacy learner profiles into portable state (originals retained)"
  else
    mkdir -p "$AGENT_HARNESS_HOME/state/learner-profiles"
  fi
fi

# --- 4. Global skills (agent-skills/<name> → every tool this machine has) ---
# agent-skills/ is the tool-agnostic source of truth. Claude Code and Codex
# CLI both use the same on-disk convention (a directory per skill holding
# SKILL.md), so each skill is installed as-is into every target present.
say "Installing global skills into $CLAUDE_DIR/skills/"
mkdir -p "$CLAUDE_DIR/skills"
if (( CODEX_PRESENT )); then
  say "Codex CLI detected — installing into $PORTABLE_SKILLS_DIR/"
  say "Also retaining the legacy-compatible $CODEX_DIR/skills/ copy"
  mkdir -p "$PORTABLE_SKILLS_DIR"
  mkdir -p "$CODEX_DIR/skills"
fi
for skill_dir in "$REPO_ROOT"/agent-skills/*/; do
  name="$(basename "$skill_dir")"
  place_tree "$skill_dir" "$CLAUDE_DIR/skills/$name"
  if (( CODEX_PRESENT )); then
    place_tree "$skill_dir" "$PORTABLE_SKILLS_DIR/$name"
    place_tree "$skill_dir" "$CODEX_DIR/skills/$name"
  fi
done

# --- 5. Clone kumo-skills-catalog (referenced by AGENTS.md) -----------------
CATALOG_DIR="$HOME/Documents/kumo-skills-catalog"
if [[ -d "$CATALOG_DIR/.git" ]]; then
  ok "kumo-skills-catalog already present at $CATALOG_DIR — skipping clone"
else
  say "Cloning kumo-skills-catalog → $CATALOG_DIR"
  mkdir -p "$(dirname "$CATALOG_DIR")"
  if git clone git@github.com:kumo-ai/kumo-skills-catalog.git "$CATALOG_DIR" 2>/dev/null; then
    ok "Cloned via SSH"
  elif gh repo clone kumo-ai/kumo-skills-catalog "$CATALOG_DIR"; then
    ok "Cloned via gh"
  else
    warn "Could not clone kumo-skills-catalog. Clone it manually:"
    warn "  git clone git@github.com:kumo-ai/kumo-skills-catalog.git $CATALOG_DIR"
  fi
fi

# --- 6. Final report --------------------------------------------------------
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
  "       - See the four enabled plugins (claude-hud, understand-anything," \
  "         frontend-design, crit) and their marketplaces" \
  "       - Install them automatically into $CLAUDE_DIR/plugins/cache/" \
  "  2. If a plugin does not auto-install, run inside Claude Code:" \
  "         /plugin" \
  "       and enable from the four entries listed in settings.json." \
  "  3. Verify the statusline renders. If not, check node path in" \
  "       $CLAUDE_DIR/settings.json  (statusLine.command embeds it literally)." \
  "" \
  "Files this run created or replaced (with .bak.${TS} for any prior contents):" \
  "  $HOME/AGENTS.md" \
  "  $CLAUDE_DIR/CLAUDE.md       (symlink -> $HOME/AGENTS.md)" \
  "  $CLAUDE_DIR/settings.json" \
  "  $CLAUDE_DIR/skills/*" \
  "  $CLAUDE_DIR/agents/lei-harness/*" \
  "  $AGENT_HARNESS_HOME/specs" \
  "  $AGENT_HARNESS_HOME/state/learner-profiles  (initialized, never overwritten)"
if (( CODEX_PRESENT )); then
  printf '%s\n' \
    "  $CODEX_DIR/AGENTS.md        (symlink -> $HOME/AGENTS.md)" \
    "  $CODEX_DIR/config.toml      (agents.max_depth = 2)" \
    "  $CODEX_DIR/agents/lei-harness-*.toml" \
    "  $PORTABLE_SKILLS_DIR/*" \
    "  $CODEX_DIR/skills/*         (legacy-compatible copy)"
fi
printf '\n%s\n' \
  "Not migrated (intentionally - these are per-project or per-session):" \
  "  $CLAUDE_DIR/projects/   $CLAUDE_DIR/sessions/   $CLAUDE_DIR/tasks/" \
  "  $CLAUDE_DIR/plugins/cache/   $CLAUDE_DIR/history.jsonl" \
  "  Any project-local .claude/ directories (bench-ec2, gpu-ec2, ship, learn, ...)" \
  ""
