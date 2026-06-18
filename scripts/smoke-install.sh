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
SMOKE_VAULT="$SMOKE_DIR/noesis-vault"

"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/python" -m pip install -e "$ROOT"

cp -R "$EXAMPLE_VAULT" "$SMOKE_VAULT"

(
  unset PYTHONPATH
  "$VENV/bin/noesis" vault doctor "$SMOKE_VAULT" --json > "$SMOKE_DIR/doctor.json"
  "$VENV/bin/noesis" vault validate "$SMOKE_VAULT"
  "$VENV/bin/noesis" context build \
    --vault "$SMOKE_VAULT" \
    --scope agent-memory \
    --purpose "installed console-script smoke" \
    --limit 1 \
    --json > "$SMOKE_DIR/context.json"
  "$VENV/bin/noesis" trace reviewed-knowledge-agent-memory-dogfood \
    --vault "$SMOKE_VAULT" \
    --json > "$SMOKE_DIR/trace.json"
  "$VENV/bin/noesis" review show claim-agent-memory-dogfood \
    --vault "$SMOKE_VAULT" \
    --json > "$SMOKE_DIR/review-show.json"
  NOESIS_MCP_BIN="$VENV/bin/noesis-mcp" \
    NOESIS_MCP_VAULT="$SMOKE_VAULT" \
    NOESIS_MCP_OUTPUT="$SMOKE_DIR/mcp-stdio.json" \
    "$VENV/bin/python" - <<'PY'
import json
import os
import selectors
import subprocess
import sys
import time


command = [os.environ["NOESIS_MCP_BIN"], os.environ["NOESIS_MCP_VAULT"]]
process = subprocess.Popen(
    command,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
assert process.stdin is not None
assert process.stdout is not None
assert process.stderr is not None


def send(message):
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "noesis-smoke", "version": "0"},
        },
    }
)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
send(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "noesis_build_context",
            "arguments": {
                "scope": "agent-memory",
                "purpose": "installed MCP stdio smoke",
                "limit": 1,
            },
        },
    }
)
send({"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "noesis://vault/summary"}})

selector = selectors.DefaultSelector()
selector.register(process.stdout, selectors.EVENT_READ, "stdout")
selector.register(process.stderr, selectors.EVENT_READ, "stderr")
responses = {}
stderr_lines = []
deadline = time.monotonic() + 15
while time.monotonic() < deadline and not {1, 2, 3, 4}.issubset(responses):
    for key, _ in selector.select(timeout=0.25):
        line = key.fileobj.readline()
        if not line:
            continue
        if key.data == "stderr":
            stderr_lines.append(line)
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in message:
            responses[message["id"]] = message

try:
    process.stdin.close()
except BrokenPipeError:
    pass
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    process.terminate()
    process.wait(timeout=5)

missing = sorted({1, 2, 3, 4} - set(responses))
if missing:
    sys.stderr.write(f"missing MCP responses: {missing}\n")
    sys.stderr.write("".join(stderr_lines))
    raise SystemExit(1)

wire_payload = json.dumps(responses, sort_keys=True)
if "noesis_build_context" not in wire_payload:
    raise SystemExit("MCP tools/list did not include noesis_build_context")
if "reviewed-knowledge-agent-memory-dogfood" not in wire_payload:
    raise SystemExit("MCP context call did not return agent-memory reviewed knowledge")
if "note_count" not in wire_payload:
    raise SystemExit("MCP resource read did not return a vault summary")

with open(os.environ["NOESIS_MCP_OUTPUT"], "w", encoding="utf-8") as handle:
    json.dump(responses, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
)

echo "Noesis editable-install smoke passed"
echo "venv: $VENV"
echo "temp vault: $SMOKE_VAULT"
echo "doctor JSON: $SMOKE_DIR/doctor.json"
echo "context JSON: $SMOKE_DIR/context.json"
echo "trace JSON: $SMOKE_DIR/trace.json"
echo "review JSON: $SMOKE_DIR/review-show.json"
echo "MCP stdio JSON: $SMOKE_DIR/mcp-stdio.json"
