---
title: Operational Context - Project Memory Corpus Continuation
noesis_id: context-project-memory-corpus-continuation
type: operational-context
lifecycle_stage: context
status: active
review_state: reviewed
confidence: high
created: 2026-06-18
updated: 2026-06-18
scope: project-memory-corpus
purpose: continue expanding Noesis Foundry project memory
context_limit: 1
syntheses:
  - "[[synthesis-project-memory-corpus-continuation]]"
reviewed_knowledge:
  - "[[reviewed-knowledge-project-memory-corpus-continuation]]"
excluded_memory:
  - "[[archive-2026-05-29-first-lifecycle]]"
  - "[[stale-agent-memory-global-summary]]"
  - "[[stale-custom-plugin-first]]"
  - "[[stale-noesis-roadmap-plugin-first]]"
  - "[[stale-project-memory-corpus-bulk-import-active-context]]"
freshness_excluded: []
as_of: 2026-06-18
freshness_policy: balanced
input_hashes:
  - "reviewed-knowledge-project-memory-corpus-continuation=sha256:d2abde538021ef7203a845ba10a8628cce5c1319afea7e3a64d5ca79e42632ef"
next_review: 2026-07-18
tags:
  - noesis
  - context
  - project-memory-corpus
  - continuation
aliases:
  - project memory corpus continuation context
---

# Noesis Operational Context

Scope: project-memory-corpus

Purpose: continue expanding Noesis Foundry project memory

As of: 2026-06-18
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

### Project Memory Corpus Continuation Knowledge

- noesis_id: reviewed-knowledge-project-memory-corpus-continuation
- path: knowledge/reviewed-knowledge-project-memory-corpus-continuation.md
- confidence: high
- reviewed_at: 2026-06-18
- freshness: fresh

# Project Memory Corpus Continuation Knowledge

## Current Knowledge

Use source-backed project-memory chains to continue Noesis Foundry work. A useful
corpus entry should start from checked-in repository artifacts or local fixtures,
extract focused evidence, state a bounded claim, record review, synthesize the
result, and promote only the reviewed conclusion into active operational
context.

Captured session bundles are valuable source material because they preserve
local artifacts, provenance, branch or session metadata, and duplicate handling.
They should inform evidence and review, not bypass review by becoming active
context directly.

Unreviewed evidence drafts, such as imported artifact candidates awaiting
review, remain preserved inputs. They are not active operational context until a
claim, review, synthesis, and reviewed-knowledge promotion accepts the guidance.

## Why It Is Trusted

- It is grounded in [[source-project-memory-corpus-repo-artifacts]], [[source-project-memory-corpus-bundle-fixture]], and [[source-project-memory-corpus-review-governance]].
- The supporting evidence is recorded in [[evidence-project-memory-corpus-contract]], [[evidence-project-memory-corpus-import-fixture]], and [[evidence-project-memory-corpus-review-gate]].
- The claim is approved in [[review-project-memory-corpus-continuation]].
- The synthesis is [[synthesis-project-memory-corpus-continuation]].

## Use In Future Work

Use this when expanding `examples/noesis-vault`, designing source-bundle dogfood
fixtures, or preparing scoped context for an agent that needs to continue
Noesis Foundry implementation without reviving stale shortcuts.

## Staleness Rule

Recheck this note if Noesis intentionally allows raw imported artifacts or
unreviewed evidence drafts to appear as active operational context.

## Traceability

- Reviewed knowledge: [[reviewed-knowledge-project-memory-corpus-continuation]]
- Syntheses: [[synthesis-project-memory-corpus-continuation]]
- Excluded memory: [[archive-2026-05-29-first-lifecycle]], [[stale-agent-memory-global-summary]], [[stale-custom-plugin-first]], [[stale-noesis-roadmap-plugin-first]], [[stale-project-memory-corpus-bulk-import-active-context]]
