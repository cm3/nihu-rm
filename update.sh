#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/projects/nihu-rm}"
REPO_DIR="${REPO_DIR:-$APP_ROOT/repo}"
VENV_DIR="${VENV_DIR:-$APP_ROOT/venv}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"

cd "$REPO_DIR"

if [ "$ALLOW_DIRTY" != "1" ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is dirty. Commit/stash or run with ALLOW_DIRTY=1" >&2
    git status --porcelain
    exit 1
  fi
fi

echo "==> git pull --ff-only"
git fetch origin
git pull --ff-only

echo "==> check untracked files (except data/)"
UNTRACKED=$(git clean -ndx --exclude=data/)
if [ -n "$UNTRACKED" ]; then
  echo "WARNING: The following untracked files/directories will be removed:"
  echo "$UNTRACKED"
  read -p "Proceed with removal? [y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    git clean -fdx --exclude=data/
    echo "Removed."
  else
    echo "Skipped cleanup."
  fi
fi

echo "==> install/refresh deps"
"$VENV_DIR/bin/python" -m pip install -U pip wheel
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
if [ -f "app_c/requirements.txt" ]; then
  "$VENV_DIR/bin/python" -m pip install -r app_c/requirements.txt
fi

echo "==> restart services"
systemctl --user daemon-reload
systemctl --user restart nihu-rm-a nihu-rm-c
systemctl --user status nihu-rm-a --no-pager -l || true
systemctl --user status nihu-rm-c --no-pager -l || true

echo "==> done"

