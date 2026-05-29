# ADR 0001: Use Obsidian Core as the First Human Interface

Status: accepted for prototype  
Date: 2026-05-29

## Context

Noesis needs a local-first human interface for reviewing source-backed memory.
The interface must be useful to humans in Obsidian and predictable for agents
that need to read, write, validate, and prepare context from the same knowledge
base.

The system should avoid making a community plugin or custom Obsidian plugin the
durable source of truth. Community plugins can improve capture, automation, and
views, but the first Noesis contract should survive without them.

## Decision

The first Noesis Obsidian interface will use ordinary Markdown files with flat
YAML properties as the durable storage contract.

Core dependencies:

- Obsidian Markdown vaults for local files.
- Properties for lifecycle metadata.
- Bases for review queues and dashboards.
- Backlinks, search, and graph views for traceability.

Core recommended features:

- Templates for human-created notes.
- Canvas for visual lifecycle maps.

Optional adapters:

- Obsidian Web Clipper for browser capture.
- Dataview for advanced dashboards after the core Base views are proven.
- Tasks for richer review task handling.
- Obsidian Git for human-managed sync and backup.
- Local REST API or similar plugins for active-note and running-Obsidian
  integration.
- Zotero Integration for academic source capture.

Deferred:

- A custom Noesis Obsidian plugin.
- Templater and QuickAdd automation.
- Kanban-specific review boards.
- Plugin-specific query languages as part of the Noesis storage contract.

## Consequences

The CLI and MCP server can be built against files first. This keeps tests
simple and lets other agents use Noesis without controlling an Obsidian app.

Human review still gets an Obsidian-native interface through Properties, Bases,
Canvas, and wikilinks.

Community plugins remain available as adapters. If a plugin disappears, the
vault still contains complete Noesis memory.

The main tradeoff is that the first UI is less automated than a custom plugin.
That is acceptable until the lifecycle contract is proven by real use.

Community plugin risk is explicit: Obsidian's
[plugin security guidance](https://obsidian.md/help/plugin-security) says
third-party plugins inherit Obsidian's local access level. That makes core
features preferable for the storage contract and keeps community plugins in the
adapter layer.

## Build Criteria for a Future Custom Plugin

Reconsider a custom plugin only if at least one of these becomes true:

- Bases cannot express the review queues humans need.
- Human review requires inline provenance controls that Markdown and Bases
  cannot represent.
- Active-note capture becomes central to the workflow and REST adapters are not
  reliable enough.
- The CLI/MCP contract is stable and a plugin can be a thin UI over that
  contract instead of a second implementation.
