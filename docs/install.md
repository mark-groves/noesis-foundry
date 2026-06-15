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
noesis-mcp --help
```

The `doctor` command reports contract compatibility, validation completeness,
and whether the vault is ready for CLI/MCP use. `validate` checks the example
vault's Markdown frontmatter, wikilinks, Base YAML, Canvas JSON, and active
context exclusions.

For a disposable end-to-end check, run the checked-in smoke script:

```bash
bash scripts/smoke-install.sh
```

The script creates a temporary virtual environment, installs the project in
editable mode, unsets `PYTHONPATH`, then runs:

```bash
noesis vault doctor examples/noesis-vault --json
noesis vault validate examples/noesis-vault
noesis-mcp --help
```

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
