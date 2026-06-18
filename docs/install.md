# Install and Adapter Setup

This guide proves the distribution path for Noesis without relying on
`PYTHONPATH=src`. It is for developers and agents that need to install the
package, validate a vault, and connect the MCP adapter from outside this
repository.

The vault files are the source of truth. The `noesis` CLI, `noesis-mcp` server,
and repo-local Agent Skills are replaceable adapters over the same Markdown,
flat YAML, Base, and Canvas contract. They must not introduce a second schema.

## Editable Install

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
noesis vault doctor examples/noesis-vault --json
noesis vault validate examples/noesis-vault
noesis context build --vault examples/noesis-vault --scope agent-memory --limit 1 --json
noesis trace reviewed-knowledge-agent-memory-dogfood --vault examples/noesis-vault --json
noesis-mcp "$(pwd)/examples/noesis-vault"
```

The `doctor` command reports contract compatibility, validation completeness,
and whether the vault is ready for CLI/MCP use. `validate` checks the example
vault's Markdown frontmatter, wikilinks, Base YAML, Canvas JSON, and active
context exclusions. The `context build` and `trace` commands prove the
installed console script can read reviewed knowledge and lineage through the
same lifecycle adapter an agent will use.

For a disposable end-to-end check, run the checked-in smoke script:

```bash
bash scripts/smoke-install.sh
```

The script creates a temporary virtual environment, installs the project in
editable mode, copies the example vault to a temporary vault, unsets
`PYTHONPATH`, then runs:

```bash
noesis vault doctor "$TEMP_VAULT" --json
noesis vault validate "$TEMP_VAULT"
noesis context build --vault "$TEMP_VAULT" --scope agent-memory --limit 1 --json
noesis trace reviewed-knowledge-agent-memory-dogfood --vault "$TEMP_VAULT" --json
noesis review show claim-agent-memory-dogfood --vault "$TEMP_VAULT" --json
noesis-mcp "$TEMP_VAULT"
```

The final step starts the installed `noesis-mcp` stdio server, performs a local
JSON-RPC handshake, lists tools, calls `noesis_build_context`, and reads
`noesis://vault/summary`. It does not require a desktop MCP client and does not
write to the repository checkout.

Set `PYTHON=/path/to/python` to choose a Python interpreter. Set
`NOESIS_SMOKE_DIR=/path/to/dir` to keep the generated virtual environment and
smoke outputs for inspection.

## Console Scripts

The package exposes two console scripts:

| Script | Entry point | Purpose |
| --- | --- | --- |
| `noesis` | `noesis.cli:main` | Read, validate, create, review, trace, and build context from Noesis vault files. |
| `noesis-mcp` | `noesis.mcp_server:main` | Start the stdio MCP adapter over a default Noesis vault. |

Both scripts operate on vault files. Obsidian does not need to be running.

## MCP Server

Start the server against the example vault after installation:

```bash
noesis-mcp "$(pwd)/examples/noesis-vault"
```

If no path is provided, `noesis-mcp` defaults to `examples/noesis-vault`
relative to the process working directory. Desktop MCP clients often launch
servers from another directory, so use absolute vault paths in client configs.

Tools also accept a `vault_path` argument. That lets one server operate on
another compatible vault when the client supplies a path explicitly.

For an agent smoke path, validate the vault with the CLI first, then have the
MCP client call `noesis_lint_vault`, `noesis_build_context` with the task
scope, and `noesis_trace_lineage` or `noesis_get_note` for any knowledge that
will guide edits. Treat MCP responses as adapter output over vault files, not
as a separate datastore.

## MCP Client Config

A generic stdio client example lives at
[`examples/mcp/noesis-mcp.example.json`](../examples/mcp/noesis-mcp.example.json).
Copy it into the client-specific MCP config location and replace both absolute
paths:

```json
{
  "mcpServers": {
    "noesis": {
      "command": "/absolute/path/to/.venv/bin/noesis-mcp",
      "args": ["/absolute/path/to/noesis-vault"]
    }
  }
}
```

Use the console script from the virtual environment where `pip install -e .`
was run. If the client supports environment variables, keep them minimal; the
installed package path should come from the console script, not from
`PYTHONPATH`.

## New Agent Workflow

For a harness-neutral "new agent uses Noesis" flow, start from the installed
CLI and the vault path. The agent runtime can be any coding or research
assistant; the workflow depends only on the vault contract and adapter
commands.

```bash
noesis vault doctor /absolute/path/to/noesis-vault --json
noesis vault validate /absolute/path/to/noesis-vault
noesis context build --vault /absolute/path/to/noesis-vault --scope "<task scope>" --purpose "<task purpose>" --json
noesis trace <reviewed-knowledge-id> --vault /absolute/path/to/noesis-vault --json
```

When MCP is available, use the same order through tools:

```text
1. noesis_lint_vault with the target vault path.
2. noesis_build_context with the task scope and purpose.
3. noesis_trace_lineage for any reviewed knowledge that will guide changes.
4. noesis_get_note when the agent needs the full source note body.
5. Use lifecycle write tools only when the task explicitly asks to update memory.
```

When portable skills are available, load the repo-local `skills/` directory.
The matching skill should choose CLI first, MCP second, and direct Markdown/YAML
fallback only when neither adapter can run. Skills should point back to the
vault contract and installed adapters instead of copying required fields into
their own schema.

## Repo-Local Skills

Repo-local skills in [`skills/`](../skills/) are distribution artifacts for
agent runtimes that support portable Agent Skills. They are not a Python
package resource and they do not duplicate the canonical schema.

Use them by pointing the agent runtime at the `skills/` directory, then keep the
skill procedure CLI-first:

```bash
noesis vault validate /absolute/path/to/noesis-vault
noesis context build --vault /absolute/path/to/noesis-vault --purpose "prepare the next task"
```

Direct Markdown/YAML edits are fallback adapter behavior only. When a skill has
to fall back, it should copy local templates where possible, preserve raw
sources, keep YAML flat, maintain wikilinks, and run `noesis vault validate`
before reporting completion.
