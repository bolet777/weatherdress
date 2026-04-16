#!/usr/bin/env bash
# Lance WeatherDress sur macOS (équivalent à : cd projet && make run).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
fi

export PYTHONPATH="$ROOT/src"
exec python3 -m weatherdress.main
