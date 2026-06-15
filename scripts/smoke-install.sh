#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

if [[ -n "${NOESIS_SMOKE_DIR:-}" ]]; then
  SMOKE_DIR="$NOESIS_SMOKE_DIR"
  mkdir -p "$SMOKE_DIR"
  CLEANUP=0
else
  SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/noesis-smoke.XXXXXX")"
  CLEANUP=1
fi

if [[ "$CLEANUP" == "1" ]]; then
  trap 'rm -rf "$SMOKE_DIR"' EXIT
fi

VENV="$SMOKE_DIR/venv"
EXAMPLE_VAULT="$ROOT/examples/noesis-vault"

"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install -e "$ROOT"

(
  unset PYTHONPATH
  "$VENV/bin/noesis" vault doctor "$EXAMPLE_VAULT" --json > "$SMOKE_DIR/doctor.json"
  "$VENV/bin/noesis" vault validate "$EXAMPLE_VAULT"
  "$VENV/bin/noesis-mcp" --help > "$SMOKE_DIR/noesis-mcp-help.txt"
)

echo "Noesis editable-install smoke passed"
echo "venv: $VENV"
echo "doctor JSON: $SMOKE_DIR/doctor.json"
echo "MCP help: $SMOKE_DIR/noesis-mcp-help.txt"
