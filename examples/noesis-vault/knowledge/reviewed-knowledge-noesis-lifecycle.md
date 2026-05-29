---
title: Noesis Lifecycle Knowledge
noesis_id: reviewed-knowledge-noesis-lifecycle
type: reviewed-knowledge
lifecycle_stage: knowledge
status: active
review_state: reviewed
confidence: high
created: 2026-05-29
updated: 2026-05-29
sources:
  - "[[source-noesis-readme]]"
evidence:
  - "[[evidence-memory-lifecycle]]"
claims:
  - "[[claim-useful-memory-requires-lifecycle]]"
syntheses:
  - "[[synthesis-local-first-lifecycle-interface]]"
reviewed_by:
  - "[[review-local-first-lifecycle]]"
reviewed_at: 2026-05-29
next_review: 2026-06-29
tags:
  - noesis
  - knowledge
aliases:
  - lifecycle knowledge
---

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

