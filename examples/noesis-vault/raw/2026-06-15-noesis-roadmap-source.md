# Noesis Roadmap Source Snapshot

This source snapshot compacts the checked-in project docs as of 2026-06-15
into roadmap material for the next Noesis phases.

## Source Basis

- `README.md` defines Noesis as a local-first memory and synthesis system that
  turns sources, evidence, claims, synthesis, reviewed knowledge, and
  operational context into durable understanding.
- `README.md` says the first working CLI is intentionally file-backed: an
  Obsidian vault is ordinary Markdown files with flat YAML frontmatter, while
  Base and Canvas files are human-facing views.
- `README.md` describes the CLI, MCP server, and repo-local portable skills as
  adapters over the same vault parser, validator, lineage tracer, review queue,
  context builder, and lifecycle write functions.
- `docs/architecture/noesis-local-first-obsidian-interface.md` states that the
  current interface makes the lifecycle inspectable in Obsidian while leaving
  agents a stable file contract they can use without opening Obsidian.
- The architecture doc says the next implementation work should stay
  adapter-oriented: portable skills and optional Obsidian app integrations can
  build on the same vault contract without moving the schema out of Markdown
  and flat YAML.
- `skills/README.md` says the skills are documentation adapters over the
  existing vault contract and should not define a second schema.

## Superseded Shortcut

An older shortcut says Noesis should prioritize a custom Obsidian plugin before
the project-memory corpus and adapter contract are stronger. That shortcut is
stale for roadmap planning because the current checked-in surface already has a
file-backed CLI, MCP adapter, portable skills, and example-vault contract.

## Roadmap Question

What should the next Noesis phase optimize for after the first local-first
CLI/MCP/skills baseline exists?
