---
title: Noesis Review Dashboard
noesis_id: dashboard-review
type: dashboard
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: 2026-05-29
updated: 2026-06-18
tags:
  - noesis
  - dashboard
---

# Noesis Review Dashboard

## Review Queue

![[review-queue.base]]

## CLI Review Workbench

Use these read-only inspection commands from the repo root when a row needs
closer inspection:

```bash
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review show stale-custom-plugin-first --vault examples/noesis-vault
```

`review summary`, `review queue`, and `review show` report overdue review
status, audit gaps, requested changes, downstream reviewed-knowledge/context
impact, and complete lineage.

Use this write action after a scheduled review confirms the note still fits
its current lifecycle role:

```bash
PYTHONPATH=src python -m noesis review renew stale-custom-plugin-first --vault examples/noesis-vault --next-review 2026-07-05
```

`review renew` records the scheduled review audit and moves `next_review`
without changing active, stale, or superseded lifecycle status.

The Base includes separate views for the open queue, scheduled review dates,
requested changes, and downstream impact cues. Those views are inspection aids;
Markdown files and flat YAML remain the durable contract.
Use the Direct audit link checks view as a frontmatter shortcut only; the CLI
review summary remains authoritative for audit gaps because review notes can
also link targets through `reviewed_notes`.

## Lifecycle Dashboard

![[lifecycle-dashboard.base]]

## Traceability Workbench

![[traceability-workbench.base]]

Use this Base to inspect lineage links, review audit notes, active context
packages, and excluded memory before changing lifecycle state. It is a view over
frontmatter and wikilinks only; notes remain canonical.

## Current Complete Lineage

[[source-noesis-readme]] -> [[evidence-memory-lifecycle]] -> [[claim-useful-memory-requires-lifecycle]] -> [[synthesis-local-first-lifecycle-interface]] -> [[reviewed-knowledge-noesis-lifecycle]] -> [[operational-context-first-cli-mcp-workflow]]

## Visual Map

Open [[noesis-lifecycle.canvas]].
