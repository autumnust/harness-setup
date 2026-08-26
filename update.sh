#!/usr/bin/env bash
# Sync this machine's global coding-agent harness to the latest repo state.
#
# Steady-state companion to install.sh: pull the repo, then rewrite only the
# global files that actually changed (showing a diff and backing up each first).
# Safe to run anytime — it is a no-op when already in sync.
#
# Usage:
#   ./update.sh            # git pull --ff-only, then ./install.sh --update
#   ./update.sh --no-pull  # skip the pull (e.g. you just edited the repo
#                          # locally and only want to push changes into ~/).
#   ./update.sh --with-tss # also refresh the lockfile-pinned TSS companion.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PULL=1
WITH_TSS=0
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=0 ;;
    --with-tss) WITH_TSS=1 ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;34m>>\033[0m %s\n' "$*"; }

if (( PULL )); then
  say "git pull --ff-only in $REPO_ROOT"
  if ! git -C "$REPO_ROOT" pull --ff-only; then
    echo "git pull failed (uncommitted changes, or not a fast-forward)." >&2
    echo "Resolve the repo state, or re-run with --no-pull to sync as-is." >&2
    exit 1
  fi
fi

INSTALL_ARGS=(--update)
(( WITH_TSS )) && INSTALL_ARGS+=(--with-tss)
exec "$REPO_ROOT/install.sh" "${INSTALL_ARGS[@]}"
