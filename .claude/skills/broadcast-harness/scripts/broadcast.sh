#!/usr/bin/env bash
# Push this harness-setup checkout to ssh-reachable machines and run the
# installer (--update) on each, so their global Claude Code config matches
# this repo.
#
# Transport: rsync the working tree to the remote, then run install.sh --update
# there. The remote needs neither git nor GitHub access — it only receives
# files. Every reachable Host alias works uniformly because ~/.ssh/config wires
# up the SSM / IAP tunnels via ProxyCommand.
#
# Usage:
#   broadcast.sh --list                 List candidate hosts from ~/.ssh/config.
#   broadcast.sh [--check] HOST...      Deploy to the named hosts.
#   broadcast.sh [--check] --all        Deploy to every candidate host.
#     --check   Dry run: preflight reachability + rsync --dry-run (itemized),
#               but do NOT write or run the installer on the remote.
#
# Env:
#   REMOTE_DIR   Remote checkout path, relative to the remote home.
#                Default: harness-setup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
REMOTE_DIR="${REMOTE_DIR:-harness-setup}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=8)

say()  { printf '\033[1;34m>>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m✗\033[0m %s\n' "$*"; }

if [[ ! -f "$REPO_ROOT/install.sh" ]]; then
  err "Cannot find install.sh at $REPO_ROOT — is this script inside the repo?"
  exit 2
fi

# Candidate hosts: the first alias of every ~/.ssh/config Host line, skipping
# wildcard/negated patterns and github.com.
list_hosts() {
  [[ -f "$HOME/.ssh/config" ]] || return 0
  awk '
    tolower($1) == "host" {
      for (i = 2; i <= NF; i++) {
        if ($i ~ /[*!?]/)        continue
        if ($i == "github.com")  continue
        print $i
        break
      }
    }
  ' "$HOME/.ssh/config"
}

# --- arg parsing -------------------------------------------------------------
CHECK=0
ALL=0
declare -a HOSTS=()
for arg in "$@"; do
  case "$arg" in
    --list)  list_hosts; exit 0 ;;
    --check) CHECK=1 ;;
    --all)   ALL=1 ;;
    -h|--help)
      sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) err "Unknown flag: $arg"; exit 2 ;;
    *)  HOSTS+=("$arg") ;;
  esac
done

if (( ALL )); then
  while IFS= read -r h; do [[ -n "$h" ]] && HOSTS+=("$h"); done < <(list_hosts)
fi

if (( ${#HOSTS[@]} == 0 )); then
  err "No target hosts given. Use --list to see candidates, then pass host names or --all."
  exit 2
fi

(( CHECK )) && say "DRY RUN (--check): no remote will be written." || true
say "Source: $REPO_ROOT  →  remote: ~/$REMOTE_DIR"
say "Targets: ${HOSTS[*]}"
echo

# --- per-host deploy ---------------------------------------------------------
declare -a R_OK=() R_FAIL=()
for host in "${HOSTS[@]}"; do
  say "[$host] preflight…"
  if ! ssh "${SSH_OPTS[@]}" "$host" 'true' 2>/dev/null; then
    err "[$host] unreachable (ssh failed) — skipping"
    R_FAIL+=("$host (unreachable)")
    continue
  fi

  if (( CHECK )); then
    say "[$host] rsync --dry-run:"
    rsync -az --delete --itemize-changes --dry-run --exclude='.git' \
      -e "ssh ${SSH_OPTS[*]}" "$REPO_ROOT/" "$host:$REMOTE_DIR/" | sed 's/^/    /' || true
    ok "[$host] reachable; dry run complete (nothing written)"
    R_OK+=("$host (dry-run)")
    continue
  fi

  say "[$host] syncing repo…"
  if ! rsync -az --delete --exclude='.git' \
        -e "ssh ${SSH_OPTS[*]}" "$REPO_ROOT/" "$host:$REMOTE_DIR/"; then
    err "[$host] rsync failed — skipping install"
    R_FAIL+=("$host (rsync)")
    continue
  fi

  say "[$host] running install.sh --update…"
  if ssh "${SSH_OPTS[@]}" "$host" "cd \"$REMOTE_DIR\" && ./install.sh --update"; then
    ok "[$host] updated"
    R_OK+=("$host")
  else
    err "[$host] install.sh --update failed"
    R_FAIL+=("$host (install)")
  fi
  echo
done

# --- summary -----------------------------------------------------------------
echo "──────── broadcast summary ────────"
(( ${#R_OK[@]} ))   && ok   "ok:     ${R_OK[*]}"
(( ${#R_FAIL[@]} )) && err  "failed: ${R_FAIL[*]}"
(( ${#R_FAIL[@]} == 0 ))
