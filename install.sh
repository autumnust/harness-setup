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
set -euo pipefail

MODE="prompt"
for arg in "$@"; do
  case "$arg" in
    --backup)         MODE="backup" ;;
    --overwrite)      MODE="overwrite" ;;
    --skip-existing)  MODE="skip" ;;
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

# --- 1. AGENTS.md + CLAUDE.md symlink ---------------------------------------
say "Installing ~/AGENTS.md (global instructions)"
if handle_existing "$HOME/AGENTS.md"; then
  cp "$REPO_ROOT/home/AGENTS.md" "$HOME/AGENTS.md"
  ok "Wrote $HOME/AGENTS.md"
fi

say "Ensuring $CLAUDE_DIR exists"
mkdir -p "$CLAUDE_DIR"

say "Linking $CLAUDE_DIR/CLAUDE.md → $HOME/AGENTS.md"
if handle_existing "$CLAUDE_DIR/CLAUDE.md"; then
  ln -s "$HOME/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"
  ok "Symlink in place"
fi

# --- 2. settings.json (with node path patched for this device) --------------
say "Installing $CLAUDE_DIR/settings.json"
if handle_existing "$CLAUDE_DIR/settings.json"; then
  NODE_BIN="$(command -v node || true)"
  if [[ -z "$NODE_BIN" ]]; then
    warn "node not found on PATH — claude-hud statusline will not render until node is installed."
    warn "Install node (brew install node), then rerun this script to patch the path."
    NODE_BIN="/opt/homebrew/bin/node"
  fi
  say "Pinning statusline node binary to: $NODE_BIN"

  # The statusline command embeds a literal node path. Rewrite it for this device.
  python3 - "$REPO_ROOT/claude/settings.json" "$CLAUDE_DIR/settings.json" "$NODE_BIN" <<'PY'
import json, sys, re
src, dst, node_bin = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src) as f:
    cfg = json.load(f)
sl = cfg.get("statusLine", {})
cmd = sl.get("command", "")
# Replace any "/.../node" literal inside the embedded `exec "<path>" ...` call.
cmd = re.sub(r'exec\s+"[^"]*/node"', f'exec "{node_bin}"', cmd)
sl["command"] = cmd
cfg["statusLine"] = sl
with open(dst, "w") as f:
    json.dump(cfg, f, indent=2)
PY
  ok "Wrote $CLAUDE_DIR/settings.json"
fi

# --- 3. Global skills (~/.claude/skills/<name>) ------------------------------
say "Installing global skills into $CLAUDE_DIR/skills/"
mkdir -p "$CLAUDE_DIR/skills"
for skill_dir in "$REPO_ROOT"/claude/skills/*/; do
  name="$(basename "$skill_dir")"
  target="$CLAUDE_DIR/skills/$name"
  if handle_existing "$target"; then
    cp -R "$skill_dir" "$target"
    ok "Installed skill: $name"
  fi
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
