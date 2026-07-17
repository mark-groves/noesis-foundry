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
scope: lifecycle
context_limit: 1
syntheses:
  - "[[synthesis-local-first-lifecycle-interface]]"
reviewed_knowledge:
  - "[[reviewed-knowledge-noesis-lifecycle]]"
excluded_memory:
  - "[[archive-2026-05-29-first-lifecycle]]"
  - "[[stale-agent-memory-global-summary]]"
  - "[[stale-custom-plugin-first]]"
  - "[[stale-noesis-roadmap-plugin-first]]"
  - "[[stale-project-memory-corpus-bulk-import-active-context]]"
freshness_excluded: []
as_of: 2026-05-29
freshness_policy: balanced
input_hashes:
  - "reviewed-knowledge-noesis-lifecycle=sha256:8fd5a670e2e5bef05c2aae60861f3687268b07850fd0ee675a5340a4e74b8c1f"
next_review: 2026-06-29
tags:
  - noesis
  - context
  - agent-handoff
aliases:
  - first CLI MCP context
---

# Noesis Operational Context

Scope: lifecycle

As of: 2026-05-29
Freshness policy: balanced

Budget: limit 1

This context package is built from reviewed knowledge only.
Stale, superseded, archived, and expired memory is excluded.
Review-due knowledge is explicitly marked and is excluded when strict freshness is requested.

## Selection Summary

- Current reviewed knowledge available: 4
- Included in active context: 1
- Excluded by scope or budget: 3
- Excluded by freshness: 0

## Reviewed Knowledge

### Noesis Lifecycle Knowledge

- noesis_id: reviewed-knowledge-noesis-lifecycle
- path: knowledge/reviewed-knowledge-noesis-lifecycle.md
- confidence: high
- reviewed_at: 2026-05-29
- freshness: fresh

# Noesis Lifecycle Knowledge

## Current Knowledge

Noesis should represent memory as a lifecycle with explicit stages for source
material, extracted evidence, source-backed claims, synthesis, reviewed
knowledge, operational context, stale or superseded memory, and archived
history.

## Why It Is Trusted

- It is grounded in [[source-noesis-readme]].
- The supporting evidence is recorded in [[evidence-memory-lifecycle]].
- The interpretation was approved in [[review-local-first-lifecycle]].

## Use In Future Work

Use this as current guidance when implementing vault initialization, ingest,
review queues, context building, and stale-memory exclusion.

## Staleness Rule

Recheck this note if the CLI/MCP implementation discovers that the schema is
too rigid, too loose, or incompatible with Obsidian Bases.

## Traceability

- Reviewed knowledge: [[reviewed-knowledge-noesis-lifecycle]]
- Syntheses: [[synthesis-local-first-lifecycle-interface]]
- Excluded memory: [[archive-2026-05-29-first-lifecycle]], [[stale-agent-memory-global-summary]], [[stale-custom-plugin-first]], [[stale-noesis-roadmap-plugin-first]], [[stale-project-memory-corpus-bulk-import-active-context]]
