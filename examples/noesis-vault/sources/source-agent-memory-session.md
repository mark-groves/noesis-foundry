---
title: Agent Memory Dogfood Session Source
noesis_id: source-agent-memory-session
type: source
lifecycle_stage: source
status: captured
review_state: none
confidence: unknown
created: 2026-06-13
updated: 2026-06-13
source_type: dogfood-fixture
raw_path: "../raw/2026-06-13-agent-memory-session.md"
original_url: local-example-vault
author: noesis-example
source_date: 2026-06-13
captured: 2026-06-13
tags:
  - noesis
  - source
  - agent-memory
aliases:
  - agent memory dogfood source
---

# Agent Memory Dogfood Session Source

Raw source: [2026-06-13-agent-memory-session.md](../raw/2026-06-13-agent-memory-session.md)

## Summary

This source models a project session where an agent turns session artifacts into
Noesis memory before a future agent consumes context.

## Key Claims

- Future agents need reviewed handoff knowledge, not raw transcript snippets.
- Stale shortcuts should remain traceable but excluded from generated context.

## Evidence Candidates

- The source names the full lifecycle from capture through operational context.
- The source identifies direct global-summary copying as stale.

## Open Questions

- What additional adapters should write this lifecycle outside the CLI?
