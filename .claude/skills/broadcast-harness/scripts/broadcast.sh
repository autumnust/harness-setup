#!/usr/bin/env bash
# Push this harness-setup checkout to ssh-reachable machines and run the
# installer (--update) on each, so their global Claude Code config matches
# this repo.
#
# Transport: rsync the working tree to the remote, then run install.sh --update
# there. The remote needs neither git nor GitHub access — it only receives
# files. Every reachable Host alias works uniformly through the local SSH
# configuration.
#
# Usage:
#   broadcast.sh --list                             List candidate hosts from ~/.ssh/config.
#   broadcast.sh [--check] [--instance NAME] HOST... Deploy to the named hosts.
#   broadcast.sh [--check] [--instance NAME] --all   Deploy to every candidate host.
#     --check   Dry run: preflight reachability + rsync --dry-run (itemized),
#               but do NOT write or run the installer on the remote.
#     --instance Install instances/NAME.md, or its local NAME.local.md fallback,
#               on each selected target.
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
INSTANCE_PROFILE=""
declare -a HOSTS=()
while (($#)); do
  case "$1" in
    --list)  list_hosts; exit 0 ;;
    --check) CHECK=1 ;;
    --all)   ALL=1 ;;
    --instance)
      [[ $# -ge 2 ]] || { err "Missing profile name after --instance"; exit 2; }
      INSTANCE_PROFILE="$2"
      [[ "$INSTANCE_PROFILE" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
        err "Invalid instance profile name: $INSTANCE_PROFILE"
        exit 2
      }
      shift
      ;;
    -h|--help)
      awk '
        /^# Usage:/ { printing = 1 }
        /^set -euo pipefail$/ { exit }
        printing { sub(/^# ?/, ""); print }
      ' "${BASH_SOURCE[0]}"
      exit 0 ;;
    -*) err "Unknown flag: $1"; exit 2 ;;
    *)  HOSTS+=("$1") ;;
  esac
  shift
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
[[ -n "$INSTANCE_PROFILE" ]] && say "Instance profile: $INSTANCE_PROFILE"
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

  install_args="--update"
  [[ -n "$INSTANCE_PROFILE" ]] && install_args+=" --instance $INSTANCE_PROFILE"
  say "[$host] running install.sh ${install_args}…"
  if ssh "${SSH_OPTS[@]}" "$host" "cd \"$REMOTE_DIR\" && ./install.sh $install_args"; then
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
