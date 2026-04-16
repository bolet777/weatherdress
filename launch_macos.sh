#!/usr/bin/env bash
# Lance WeatherDress sur macOS (équivalent à : cd projet && make run).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source ".venv/bin/activate"
fi

exec python3 main.py
