#!/usr/bin/env bash
# Installs Lei's global Claude Code harness setup onto this machine.
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
Installs Lei's global Claude Code harness setup onto this machine.

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
TS="$(date +%Y%m%dT%H%M%S)"

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
for skill_dir in "$REPO_ROOT"/claude/skills/*/; do
  record_conflict "$CLAUDE_DIR/skills/$(basename "$skill_dir")"
done

if (( ${#CONFLICTS[@]} > 0 )) && [[ "$MODE" == "prompt" ]]; then
  warn "Existing global Claude Code setup detected on this device:"
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

# --- 1. AGENTS.md + CLAUDE.md symlink ---------------------------------------
say "Installing ~/AGENTS.md (global instructions)"
place_file "$REPO_ROOT/home/AGENTS.md" "$HOME/AGENTS.md"

say "Ensuring $CLAUDE_DIR exists"
mkdir -p "$CLAUDE_DIR"

say "Linking $CLAUDE_DIR/CLAUDE.md → $HOME/AGENTS.md"
if [[ "$MODE" == "update" ]]; then
  # The link target is content-stable; only (re)create it if it's wrong/missing.
  if [[ -L "$CLAUDE_DIR/CLAUDE.md" && "$(readlink "$CLAUDE_DIR/CLAUDE.md")" == "$HOME/AGENTS.md" ]]; then
    ok "in sync: $CLAUDE_DIR/CLAUDE.md (symlink)"
  else
    [[ -e "$CLAUDE_DIR/CLAUDE.md" || -L "$CLAUDE_DIR/CLAUDE.md" ]] && mv "$CLAUDE_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md.bak.${TS}"
    ln -s "$HOME/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"
    ok "Symlink (re)created"
  fi
elif handle_existing "$CLAUDE_DIR/CLAUDE.md"; then
  ln -s "$HOME/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"
  ok "Symlink in place"
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
RENDERED_SETTINGS="$(mktemp)"
trap 'rm -f "$RENDERED_SETTINGS"' EXIT
python3 - "$REPO_ROOT/claude/settings.json" "$RENDERED_SETTINGS" "$NODE_BIN" "$CLAUDE_DIR/settings.json" <<'PY'
import json, sys, re, os
src, dst, node_bin, existing = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(src) as f:
    cfg = json.load(f)
sl = cfg.get("statusLine", {})
cmd = sl.get("command", "")
# Replace any "/.../node" literal inside the embedded `exec "<path>" ...` call.
cmd = re.sub(r'exec\s+"[^"]*/node"', f'exec "{node_bin}"', cmd)
sl["command"] = cmd
cfg["statusLine"] = sl
# Additive merge: keep plugins/marketplaces this machine already enabled.
# Repo values win on key conflicts; host-only entries are preserved.
if os.path.exists(existing):
    try:
        with open(existing) as f:
            cur = json.load(f)
    except (ValueError, OSError):
        cur = {}
    for field in ("enabledPlugins", "extraKnownMarketplaces"):
        merged = dict(cur.get(field, {}))   # host entries first (stable order)
        merged.update(cfg.get(field, {}))   # repo entries win on conflict
        if merged:
            cfg[field] = merged
with open(dst, "w") as f:
    json.dump(cfg, f, indent=2)
PY
place_file "$RENDERED_SETTINGS" "$CLAUDE_DIR/settings.json"

# --- 3. Global skills (~/.claude/skills/<name>) ------------------------------
say "Installing global skills into $CLAUDE_DIR/skills/"
mkdir -p "$CLAUDE_DIR/skills"
for skill_dir in "$REPO_ROOT"/claude/skills/*/; do
  name="$(basename "$skill_dir")"
  place_tree "$skill_dir" "$CLAUDE_DIR/skills/$name"
done

# --- 4. Clone kumo-skills-catalog (referenced by AGENTS.md) -----------------
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

# --- 5. Final report --------------------------------------------------------
if [[ "$MODE" == "update" ]]; then
  cat <<EOF

$(ok "Harness sync complete: $UPDATED updated, $UNCHANGED already in sync.")

EOF
  if (( UPDATED > 0 )); then
    cat <<EOF
Prior contents of any changed file were saved as <path>.bak.${TS}.
Restart Claude Code so it re-reads the updated global config.
EOF
  fi
  exit 0
fi

cat <<EOF

$(ok "Global Claude Code harness installed.")

Next steps:
  1. Launch Claude Code in any directory. On first launch it will:
       - Read $CLAUDE_DIR/settings.json
       - See the four enabled plugins (claude-hud, understand-anything,
         frontend-design, crit) and their marketplaces
       - Install them automatically into $CLAUDE_DIR/plugins/cache/
  2. If a plugin does not auto-install, run inside Claude Code:
         /plugin
       and enable from the four entries listed in settings.json.
  3. Verify the statusline renders. If not, check node path in
       $CLAUDE_DIR/settings.json  (statusLine.command embeds it literally).

Files this run created or replaced (with .bak.${TS} for any prior contents):
  $HOME/AGENTS.md
  $CLAUDE_DIR/CLAUDE.md       (symlink → $HOME/AGENTS.md)
  $CLAUDE_DIR/settings.json
  $CLAUDE_DIR/skills/*

Not migrated (intentionally — these are per-project or per-session):
  $CLAUDE_DIR/projects/   $CLAUDE_DIR/sessions/   $CLAUDE_DIR/tasks/
  $CLAUDE_DIR/plugins/cache/   $CLAUDE_DIR/history.jsonl
  Any project-local .claude/ directories (bench-ec2, gpu-ec2, ship, learn, …)

EOF
