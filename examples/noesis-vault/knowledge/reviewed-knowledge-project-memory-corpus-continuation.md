---
title: Project Memory Corpus Continuation Knowledge
noesis_id: reviewed-knowledge-project-memory-corpus-continuation
type: reviewed-knowledge
lifecycle_stage: knowledge
status: active
review_state: reviewed
confidence: high
created: 2026-06-18
updated: 2026-06-18
sources:
  - "[[source-project-memory-corpus-repo-artifacts]]"
  - "[[source-project-memory-corpus-bundle-fixture]]"
evidence:
  - "[[evidence-project-memory-corpus-contract]]"
  - "[[evidence-project-memory-corpus-import-fixture]]"
claims:
  - "[[claim-project-memory-corpus-continuation]]"
syntheses:
  - "[[synthesis-project-memory-corpus-continuation]]"
reviewed_by:
  - "[[review-project-memory-corpus-continuation]]"
supersedes:
  - "[[stale-project-memory-corpus-bulk-import-active-context]]"
reviewed_at: 2026-06-18
next_review: 2026-07-18
tags:
  - noesis
  - knowledge
  - project-memory-corpus
  - continuation
aliases:
  - project memory corpus continuation knowledge
---

# Project Memory Corpus Continuation Knowledge

## Current Knowledge

Use source-backed project-memory chains to continue Noesis Foundry work. A useful
corpus entry should start from checked-in repository artifacts or local fixtures,
extract focused evidence, state a bounded claim, record review, synthesize the
result, and promote only the reviewed conclusion into active operational
context.

Captured Codex session bundles are valuable source material because they
preserve local artifacts, provenance, branch/session metadata, and duplicate
handling. They should inform evidence and review, not bypass review by becoming
active context directly.

## Why It Is Trusted

- It is grounded in [[source-project-memory-corpus-repo-artifacts]] and [[source-project-memory-corpus-bundle-fixture]].
- The supporting evidence is recorded in [[evidence-project-memory-corpus-contract]] and [[evidence-project-memory-corpus-import-fixture]].
- The claim is approved in [[review-project-memory-corpus-continuation]].
- The synthesis is [[synthesis-project-memory-corpus-continuation]].

## Use In Future Work

Use this when expanding `examples/noesis-vault`, designing source-bundle dogfood
fixtures, or preparing scoped context for an agent that needs to continue
Noesis Foundry implementation without reviving stale shortcuts.

## Staleness Rule

Recheck this note if Noesis intentionally allows raw imported artifacts or
unreviewed evidence drafts to appear as active operational context.
