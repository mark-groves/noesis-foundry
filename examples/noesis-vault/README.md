# Noesis Example Vault

This is a small Obsidian-compatible vault demonstrating one complete Noesis
lifecycle:

```text
source -> evidence -> claim -> synthesis -> reviewed knowledge -> operational context
```

It also includes a second minimal `source -> evidence -> claim` chain created
by the write-side CLI commands. That fixture starts at
`sources/source-cli-authoring-loop.md` and proves the CLI can author new
source-backed draft memory outside the original hand-written demo.

The `agent-memory` dogfood extension models a realistic project-session handoff:
`source -> evidence -> claim -> review -> synthesis -> reviewed knowledge ->
operational context`. It starts at `sources/source-agent-memory-session.md`,
ends at `context/operational-context-agent-memory-dogfood.md`, and keeps
`stale/stale-agent-memory-global-summary.md` traceable but excluded from
generated context.

Open this folder as a vault in Obsidian, then start at
`_dashboards/noesis-review-dashboard.md`.

The durable source of truth is Markdown plus YAML properties. The `_bases`,
`_canvas`, and `_dashboards` folders are human views over those notes.

## Important Files

- `_dashboards/noesis-review-dashboard.md` - human review entry point.
- `_bases/review-queue.base` - Base views for notes needing review and
  scheduled `next_review` dates.
- `_bases/lifecycle-dashboard.base` - Base view grouped by lifecycle stage.
- `_canvas/noesis-lifecycle.canvas` - visual map of the example lifecycle.
- `_templates/` - note templates for humans and agents.
- `context/operational-context-first-cli-mcp-workflow.md` - the final context
  package the next agent would read.
- `context/operational-context-agent-memory-dogfood.md` - a scoped dogfood
  context package for agent-memory work.

The CLI review workbench mirrors the Obsidian view without becoming canonical
storage:

```bash
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review show stale-custom-plugin-first --vault examples/noesis-vault
```

Use `review show` before approving or requesting changes when you need the
note's lineage, evidence support, audit trail, downstream context impact, and
changes requested in one place.

Template note: Obsidian core Templates will replace `{{title}}` and `{{date}}`.
Placeholders in angle brackets, such as `<slug>`, are for humans, the future
CLI, or agent skills to fill.
