---
title: Local-First Lifecycle Interface
noesis_id: synthesis-local-first-lifecycle-interface
type: synthesis
lifecycle_stage: synthesis
status: reviewed
review_state: approved
confidence: high
created: 2026-05-29
updated: 2026-05-29
sources:
  - "[[source-noesis-readme]]"
evidence:
  - "[[evidence-memory-lifecycle]]"
claims:
  - "[[claim-useful-memory-requires-lifecycle]]"
reviewed_by:
  - "[[review-local-first-lifecycle]]"
tags:
  - noesis
  - synthesis
aliases:
  - first lifecycle synthesis
---

# Local-First Lifecycle Interface

## Synthesis

The first Noesis interface should keep lifecycle state in local Markdown and
YAML properties. Obsidian can then provide human review through Properties,
Bases, Canvas, links, and search while agents use the same files through CLI,
MCP, or portable skills.

## Supporting Claims

- [[claim-useful-memory-requires-lifecycle]]

## Tensions Or Gaps

- The Base views are enough for initial review queues, but richer review flows
  may later need an optional plugin adapter or custom Obsidian plugin.
- The example schema is intentionally flat for portability; richer validation
  belongs in the CLI.

## Implications

- The vault schema must be stable before building MCP tools.
- Stale and superseded memory should remain in the vault but be excluded from
  active operational context.

