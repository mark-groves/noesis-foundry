---
title: Operational Context - Noesis Roadmap Phase Orchestration
noesis_id: context-noesis-roadmap-phase-orchestration
type: operational-context
lifecycle_stage: context
status: active
review_state: reviewed
confidence: high
created: 2026-06-15
updated: 2026-06-15
scope: noesis-roadmap
purpose: orchestrate next Noesis phases
syntheses:
  - "[[synthesis-noesis-roadmap-phase-orchestration]]"
reviewed_knowledge:
  - "[[reviewed-knowledge-noesis-roadmap-phase-orchestration]]"
excluded_memory:
  - "[[archive-2026-05-29-first-lifecycle]]"
  - "[[stale-agent-memory-global-summary]]"
  - "[[stale-custom-plugin-first]]"
  - "[[stale-noesis-roadmap-plugin-first]]"
  - "[[stale-project-memory-corpus-bulk-import-active-context]]"
freshness_excluded: []
as_of: 2026-06-15
freshness_policy: balanced
input_hashes:
  - "reviewed-knowledge-noesis-roadmap-phase-orchestration=sha256:cdaf20af3d615b8e92f6c7f1f80da7908def9cfdac310706ac6a380fb1fa5bea"
next_review: 2026-07-15
tags:
  - noesis
  - context
  - noesis-roadmap
  - project-memory
aliases:
  - noesis roadmap phase context
---

# Noesis Operational Context

Scope: noesis-roadmap

Purpose: orchestrate next Noesis phases

As of: 2026-06-15
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

### Noesis Roadmap Phase Orchestration Knowledge

- noesis_id: reviewed-knowledge-noesis-roadmap-phase-orchestration
- path: knowledge/reviewed-knowledge-noesis-roadmap-phase-orchestration.md
- confidence: high
- reviewed_at: 2026-06-15
- freshness: fresh

# Noesis Roadmap Phase Orchestration Knowledge

## Current Knowledge

For the next Noesis phases, prioritize source-backed project memory that helps
future agents continue this repository. Keep the example vault as the durable
contract, use Markdown plus flat YAML as the source of truth, and treat CLI,
MCP, portable skills, and future Obsidian integrations as adapters over the
same file-backed workflow.

Sequence near-term work in this order:

1. Strengthen the dogfood project-memory corpus with realistic source,
   evidence, claim, review, synthesis, reviewed knowledge, and context chains.
2. Use scoped `context build` output to brief agents on current roadmap and
   phase orchestration decisions.
3. Expand adapter coverage only where it proves the same vault contract through
   focused tests and traceable files.
4. Revisit custom Obsidian plugin work only after the file-backed review and
   context workflows expose a real product gap.

## Why It Is Trusted

- It is grounded in [[source-noesis-roadmap-docs]].
- The supporting evidence is recorded in [[evidence-noesis-roadmap-adapter-sequence]].
- The claim is approved in [[review-noesis-roadmap-phase-orchestration]].
- The synthesis is [[synthesis-noesis-roadmap-phase-orchestration]].

## Use In Future Work

Use this when planning the next Noesis implementation slice, preparing an agent
handoff, or deciding whether a proposed feature belongs in the vault contract
or in an adapter surface.

## Staleness Rule

Recheck this note if Noesis intentionally moves canonical schema authority out
of Markdown plus flat YAML, or if custom Obsidian app behavior becomes required
for the basic review and context workflow.

## Traceability

- Reviewed knowledge: [[reviewed-knowledge-noesis-roadmap-phase-orchestration]]
- Syntheses: [[synthesis-noesis-roadmap-phase-orchestration]]
- Excluded memory: [[archive-2026-05-29-first-lifecycle]], [[stale-agent-memory-global-summary]], [[stale-custom-plugin-first]], [[stale-noesis-roadmap-plugin-first]], [[stale-project-memory-corpus-bulk-import-active-context]]
