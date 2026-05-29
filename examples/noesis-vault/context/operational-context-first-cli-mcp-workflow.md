---
title: Operational Context - First CLI/MCP Workflow
noesis_id: context-first-cli-mcp-workflow
type: operational-context
lifecycle_stage: context
status: active
review_state: reviewed
confidence: high
created: 2026-05-29
updated: 2026-05-29
syntheses:
  - "[[synthesis-local-first-lifecycle-interface]]"
reviewed_knowledge:
  - "[[reviewed-knowledge-noesis-lifecycle]]"
excluded_memory:
  - "[[stale-custom-plugin-first]]"
next_review: 2026-06-29
tags:
  - noesis
  - context
  - agent-handoff
aliases:
  - first CLI MCP context
---

# Operational Context - First CLI/MCP Workflow

## Use This Context For

Use this note when implementing the first Noesis CLI and MCP workflow.

## Current Guidance

- Treat Markdown files with flat YAML properties as the durable source of truth.
- Build CLI commands against the vault schema before exposing MCP tools.
- Let Obsidian Bases and dashboards read from note properties rather than
  maintaining a second review database.
- Context building should include reviewed knowledge and exclude notes marked
  stale, superseded, or archived.

## Do Not Use

- Do not build a custom Obsidian plugin for the first implementation slice.
- Do not make Dataview, Tasks, or Templater required for the storage contract.
- Do not let stale notes shape generated operational context unless they are
  included explicitly as historical background.

## Traceability

- Reviewed knowledge: [[reviewed-knowledge-noesis-lifecycle]]
- Synthesis: [[synthesis-local-first-lifecycle-interface]]
- Review: [[review-local-first-lifecycle]]
- Superseded memory excluded from context: [[stale-custom-plugin-first]]

