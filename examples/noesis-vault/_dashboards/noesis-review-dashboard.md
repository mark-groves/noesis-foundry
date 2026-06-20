---
title: Noesis Review Workbench
noesis_id: dashboard-review
type: dashboard
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: 2026-05-29
updated: 2026-06-20
tags:
  - noesis
  - dashboard
---

# Noesis Review Workbench

Start here when deciding what the vault remembers, whether it is current, and
what should still guide active work. The embedded Bases are human inspection
views over Markdown notes and flat YAML properties; they do not store canonical
state.

## Review Queue

![[review-queue.base]]

Use this Base to triage open review work, scheduled `next_review` dates,
requested changes, downstream impact cues, and direct frontmatter audit gaps.

## CLI Review Workbench

Use these read-only inspection commands from the repo root when a row needs
closer inspection:

```bash
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review show stale-custom-plugin-first --vault examples/noesis-vault
PYTHONPATH=src python -m noesis knowledge gaps --vault examples/noesis-vault
```

`review summary`, `review queue`, and `review show` report overdue review
status, audit gaps, requested changes, downstream reviewed-knowledge/context
impact, and complete lineage.

`knowledge gaps` reports unresolved questions, weak areas, and contradictions
from source-backed gap notes without including them in active context.

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

Use the lifecycle views to compare stage, status, review state, confidence,
current trusted context candidates, and stale/superseded/archive exceptions
before letting memory guide new work.

## Traceability Workbench

![[traceability-workbench.base]]

Use this Base to inspect source-to-context lineage links, review audit notes,
trust review schedules, knowledge gaps, active context packages, context
inclusion maps, and excluded memory before changing lifecycle state. It is a
view over frontmatter and wikilinks only; notes remain canonical.

## Current Complete Lineage

[[source-noesis-readme]] -> [[evidence-memory-lifecycle]] -> [[claim-useful-memory-requires-lifecycle]] -> [[synthesis-local-first-lifecycle-interface]] -> [[reviewed-knowledge-noesis-lifecycle]] -> [[operational-context-first-cli-mcp-workflow]]

## Visual Map

Open [[noesis-lifecycle.canvas]].
