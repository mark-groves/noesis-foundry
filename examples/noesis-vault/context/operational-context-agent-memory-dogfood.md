---
title: Operational Context - Agent Memory Dogfood
noesis_id: context-agent-memory-dogfood
type: operational-context
lifecycle_stage: context
status: active
review_state: reviewed
confidence: high
created: 2026-06-13
updated: 2026-06-13
scope: agent-memory
purpose: prepare a future agent to continue Noesis project work
syntheses:
  - "[[synthesis-agent-memory-dogfood]]"
reviewed_knowledge:
  - "[[reviewed-knowledge-agent-memory-dogfood]]"
excluded_memory:
  - "[[archive-2026-05-29-first-lifecycle]]"
  - "[[stale-agent-memory-global-summary]]"
  - "[[stale-custom-plugin-first]]"
  - "[[stale-noesis-roadmap-plugin-first]]"
  - "[[stale-project-memory-corpus-bulk-import-active-context]]"
freshness_excluded: []
as_of: 2026-06-13
freshness_policy: balanced
input_hashes:
  - "reviewed-knowledge-agent-memory-dogfood=sha256:dba0a59eac8c4a560f212c4c86abfecac6ff469034da7bbabfc66f36d143f419"
next_review: 2026-07-13
tags:
  - noesis
  - context
  - agent-memory
  - agent-handoff
aliases:
  - agent memory dogfood context
---

# Noesis Operational Context

Scope: agent-memory

Purpose: prepare a future agent to continue Noesis project work

As of: 2026-06-13
Freshness policy: balanced

This context package is built from reviewed knowledge only.
Stale, superseded, archived, and expired memory is excluded.
Review-due knowledge is explicitly marked and is excluded when strict freshness is requested.

## Selection Summary

- Current reviewed knowledge available: 4
- Included in active context: 1
- Excluded by scope or budget: 3
- Excluded by freshness: 0

## Reviewed Knowledge

### Agent Memory Dogfood Knowledge

- noesis_id: reviewed-knowledge-agent-memory-dogfood
- path: knowledge/reviewed-knowledge-agent-memory-dogfood.md
- confidence: high
- reviewed_at: 2026-06-13
- freshness: fresh

# Agent Memory Dogfood Knowledge

## Current Knowledge

Agents should turn session artifacts into reviewed Noesis memory before using
that memory to brief future project work. The durable handoff starts with local
source material, preserves evidence and claims, records human or agent review,
promotes the reviewed synthesis, and builds context only from current reviewed
knowledge.

## Why It Is Trusted

- It is grounded in [[source-agent-memory-session]].
- The supporting evidence is recorded in [[evidence-agent-memory-dogfood]].
- The claim is approved in [[review-agent-memory-dogfood]].
- The synthesis is [[synthesis-agent-memory-dogfood]].

## Use In Future Work

Use this when testing or documenting how Noesis supports agent memory during a
real project session.

## Staleness Rule

Recheck this note if agent adapters begin writing context directly without the
reviewed-knowledge promotion step.

## Traceability

- Reviewed knowledge: [[reviewed-knowledge-agent-memory-dogfood]]
- Syntheses: [[synthesis-agent-memory-dogfood]]
- Excluded memory: [[archive-2026-05-29-first-lifecycle]], [[stale-agent-memory-global-summary]], [[stale-custom-plugin-first]], [[stale-noesis-roadmap-plugin-first]], [[stale-project-memory-corpus-bulk-import-active-context]]
