# Project Memory Corpus Repo Artifact Source

Captured: 2026-06-18

This raw source consolidates checked-in Noesis Foundry repository artifacts that
define how future project-memory additions should be shaped.

## Repository Artifacts

- `README.md` describes Noesis as a local-first memory and synthesis system
  that turns sources, decisions, experiments, mistakes, and discoveries into
  reviewed knowledge and operational context.
- `README.md` documents `trace`, `context build`, `context explain`, and
  `context write`, with context built from current reviewed knowledge only.
- `README.md` states that vault files are the source of truth and that CLI, MCP,
  and repo-local portable Agent Skills are adapters over the same parser,
  validator, lineage tracer, review queue, context builder, and lifecycle write
  functions.
- `docs/architecture/noesis-local-first-obsidian-interface.md` defines ordinary
  Markdown files with flat YAML frontmatter as the durable vault contract.
- `skills/noesis-context/SKILL.md` tells agents to build context from reviewed
  knowledge only and to mention stale or superseded memory only as excluded
  background.

## Interpretation Boundary

These artifacts support expanding the checked-in example vault as project
memory. They do not support introducing a database, hosted service, custom
Obsidian plugin storage contract, or unreviewed raw transcript dump as active
guidance.
