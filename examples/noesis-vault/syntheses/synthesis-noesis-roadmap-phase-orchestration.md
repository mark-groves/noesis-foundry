---
title: Noesis Roadmap Phase Orchestration Synthesis
noesis_id: synthesis-noesis-roadmap-phase-orchestration
type: synthesis
lifecycle_stage: synthesis
status: reviewed
review_state: approved
confidence: high
created: 2026-06-15
updated: 2026-06-15
sources:
  - "[[source-noesis-roadmap-docs]]"
evidence:
  - "[[evidence-noesis-roadmap-adapter-sequence]]"
claims:
  - "[[claim-noesis-roadmap-project-memory-first]]"
reviewed_by:
  - "[[review-noesis-roadmap-phase-orchestration]]"
reviewed_at: 2026-06-15
tags:
  - noesis
  - synthesis
  - noesis-roadmap
  - project-memory
aliases:
  - noesis roadmap phase synthesis
---

# Noesis Roadmap Phase Orchestration Synthesis

## Synthesis

Noesis should orchestrate its next phases around stronger project memory before
larger product surfaces. The immediate path is to keep improving the example
vault as a realistic dogfood corpus, make context packages useful for agents
continuing this repository, and let CLI, MCP, and portable skills remain thin
adapters over the same file-backed contract.

## Supporting Claims

- [[claim-noesis-roadmap-project-memory-first]]

## Tensions Or Gaps

Adapter work remains valuable, but it should prove that it can read and write
the existing vault contract instead of introducing alternate storage or nested
metadata. A custom Obsidian plugin can return later if core Obsidian views and
external adapters cannot support the review workflow.

## Implications

Future implementation slices should add source-backed memory chains, context
fixtures, adapter smoke coverage, and review/lifecycle tests that keep stale
or superseded roadmap ideas out of generated operational context.
