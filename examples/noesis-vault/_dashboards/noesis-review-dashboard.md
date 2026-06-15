---
title: Noesis Review Dashboard
noesis_id: dashboard-review
type: dashboard
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: 2026-05-29
updated: 2026-06-13
tags:
  - noesis
  - dashboard
---

# Noesis Review Dashboard

## Review Queue

![[review-queue.base]]

## CLI Review Workbench

Use these read-only commands from the repo root when a row needs closer
inspection:

```bash
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review show stale-custom-plugin-first --vault examples/noesis-vault
```

`review show` reports the note state, linked support, audit records, requested
changes, downstream reviewed-knowledge/context impact, and complete lineage.

## Lifecycle Dashboard

![[lifecycle-dashboard.base]]

## Current Complete Lineage

[[source-noesis-readme]] -> [[evidence-memory-lifecycle]] -> [[claim-useful-memory-requires-lifecycle]] -> [[synthesis-local-first-lifecycle-interface]] -> [[reviewed-knowledge-noesis-lifecycle]] -> [[operational-context-first-cli-mcp-workflow]]

## Visual Map

Open [[noesis-lifecycle.canvas]].
