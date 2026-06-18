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

rm -rf "$SMOKE_VAULT"
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
import queue
import subprocess
import sys
import threading
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


output_queue = queue.Queue()


def read_lines(stream, label):
    for line in stream:
        output_queue.put((label, line))


threading.Thread(target=read_lines, args=(process.stdout, "stdout"), daemon=True).start()
threading.Thread(target=read_lines, args=(process.stderr, "stderr"), daemon=True).start()

responses = {}
stderr_lines = []


def read_responses(expected_ids, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not expected_ids.issubset(responses):
        try:
            label, line = output_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        if label == "stderr":
            stderr_lines.append(line)
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in message:
            responses[message["id"]] = message


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
read_responses({1})
initialize_response = responses.get(1, {})
if "error" in initialize_response:
    raise SystemExit(f"MCP initialize failed: {initialize_response['error']}")
if "result" not in initialize_response:
    sys.stderr.write("missing MCP initialize response\n")
    sys.stderr.write("".join(stderr_lines))
    raise SystemExit(1)

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
read_responses({1, 2, 3, 4})

try:
    process.stdin.close()
except BrokenPipeError:
    pass
mcp_timed_out = False
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    mcp_timed_out = True
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)

while True:
    try:
        label, line = output_queue.get_nowait()
    except queue.Empty:
        break
    if label == "stderr":
        stderr_lines.append(line)

if mcp_timed_out:
    sys.stderr.write("MCP server did not exit after stdin closed\n")
    sys.stderr.write("".join(stderr_lines))
    raise SystemExit(1)
if process.returncode != 0:
    sys.stderr.write(f"MCP server exited with {process.returncode}\n")
    sys.stderr.write("".join(stderr_lines))
    raise SystemExit(1)

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
