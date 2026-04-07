#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/hvinn/orchestrio.git"
PKG="orchestrio @ git+${REPO}#subdirectory=executors/python"
MIN_PY="3.11"

die()  { printf '\033[1;31mError:\033[0m %s\n' "$1" >&2; exit 1; }
info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m==>\033[0m %s\n' "$1"; }

# --- locate python --------------------------------------------------------
PY=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
      PY="$cmd"; break
    fi
  fi
done
[ -n "$PY" ] || die "Python >= ${MIN_PY} is required but not found. Install it from https://www.python.org/downloads/"

info "Found $PY ($ver)"

# --- install via pipx if available, else pip ------------------------------
if command -v pipx >/dev/null 2>&1; then
  info "Installing with pipx …"
  pipx install "${PKG}" || pipx upgrade orchestrio
else
  info "Installing with pip …"
  "$PY" -m pip install --user "${PKG}"
fi

# --- verify ----------------------------------------------------------------
if command -v orchestrio >/dev/null 2>&1; then
  ok "orchestrio installed successfully!"
  echo ""
  echo "  Try it now:"
  echo ""
  echo "    orchestrio run examples/hello.yaml"
  echo ""
else
  ok "Install finished. You may need to add ~/.local/bin to your PATH:"
  echo ""
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
fi
