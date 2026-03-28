#!/usr/bin/env bash
set -euo pipefail

# Wrapper for jibo_updater.py
# Prefers the repo-local venv if it exists.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$SCRIPT_DIR/.venv/bin/python"
if [[ -x "$PY" ]]; then
  exec "$PY" "$SCRIPT_DIR/jibo_updater.py" "$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/jibo_updater.py" "$@"
fi

exec python "$SCRIPT_DIR/jibo_updater.py" "$@"

# NOTE: The updater uses only the standard library and `paramiko`.
# If you don't have `paramiko` installed in your environment, install it:
# python3 -m pip install paramiko
