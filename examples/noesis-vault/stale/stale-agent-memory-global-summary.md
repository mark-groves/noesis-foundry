---
title: Stale Memory - Copy Global Summary Directly
noesis_id: stale-agent-memory-global-summary
type: stale-memory
lifecycle_stage: stale
status: superseded
review_state: reviewed
confidence: medium
created: 2026-06-13
updated: 2026-06-13
superseded_by:
  - "[[reviewed-knowledge-agent-memory-dogfood]]"
next_review: 2026-07-13
tags:
  - noesis
  - stale
  - agent-memory
aliases:
  - direct global summary memory
---

# Stale Memory - Copy Global Summary Directly

## Previous Assumption

Agents can safely copy global summary snippets directly into future prompts as
project memory.

## Why It Is Superseded

The agent-memory dogfood workflow keeps memory file-backed, source-backed, and
reviewed before it becomes operational context.

## Current Replacement

- [[reviewed-knowledge-agent-memory-dogfood]]

## Review Need

Keep this note available for traceability, but exclude it from generated
operational context.
