---
title: Noesis Roadmap Docs Source
noesis_id: source-noesis-roadmap-docs
type: source
lifecycle_stage: source
status: captured
review_state: none
confidence: unknown
created: 2026-06-15
updated: 2026-06-15
source_type: dogfood-fixture
raw_path: "../raw/2026-06-15-noesis-roadmap-source.md"
original_url: local-repository-docs
author: noesis-example
source_date: 2026-06-15
captured: 2026-06-15
tags:
  - noesis
  - source
  - noesis-roadmap
  - project-memory
aliases:
  - noesis roadmap docs source
---

# Noesis Roadmap Docs Source

Raw source: [2026-06-15-noesis-roadmap-source.md](../raw/2026-06-15-noesis-roadmap-source.md)

## Summary

This source captures checked-in README, architecture, and skill documentation
that explains the current Noesis implementation boundary and the next-phase
roadmap constraint.

## Key Claims

- The durable contract remains Markdown plus flat YAML in a local vault.
- Obsidian, CLI, MCP, and portable skills are adapters over that contract.
- Next roadmap work should strengthen project memory and adapter behavior
  before introducing custom app-specific schema or plugin storage.

## Evidence Candidates

- The docs explicitly call the vault the source of truth.
- The docs describe CLI, MCP, and skills as adapters over shared vault
  functions.
- The architecture notes keep future Obsidian app integrations optional and
  adapter-oriented.

## Open Questions

- Which project-memory corpus slice best prepares the next agent to continue
  roadmap and phase orchestration work?
