#!/usr/bin/env bash
set -euo pipefail

# Main GUI launcher (Main Panel)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$SCRIPT_DIR/.venv/bin/python"
if [[ -x "$PY" ]]; then
  exec "$PY" -m gui.main_panel "$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 -m gui.main_panel "$@"
fi

exec python -m gui.main_panel "$@"
