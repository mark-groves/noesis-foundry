---
title: Project Memory Corpus Bundle Fixture Source
noesis_id: source-project-memory-corpus-bundle-fixture
type: source
lifecycle_stage: source
status: captured
review_state: none
confidence: unknown
created: 2026-06-18
updated: 2026-06-18
source_type: local-fixture-summary
raw_path: "../raw/2026-06-18-project-memory-corpus-bundle-fixture.md"
original_url: local-test-fixture
author: noesis-example
source_date: 2026-06-18
captured: 2026-06-18
tags:
  - noesis
  - source
  - project-memory-corpus
  - capture-import
aliases:
  - project memory corpus bundle source
---

# Project Memory Corpus Bundle Fixture Source

Raw source: [2026-06-18-project-memory-corpus-bundle-fixture.md](../raw/2026-06-18-project-memory-corpus-bundle-fixture.md)

## Summary

This source captures the checked-in Codex session bundle fixture used to prove
that local project artifacts can be imported deterministically as source-backed
memory.

## Key Claims

- Imported project-session artifacts should preserve local raw material and
  provenance.
- Duplicate captures should be handled deterministically.
- Imported artifacts should become reviewable evidence candidates before they
  influence active context.

## Evidence Candidates

- The bundle manifest names deterministic artifact paths and evidence drafts.
- The transcript fixture requires raw artifact preservation, provenance, and
  reviewable evidence drafts without live network access.
- The duplicate transcript fixture prevents naive "more captures means more
  active context" behavior.

## Open Questions

- How should future bundle imports summarize duplicate and skipped artifacts for
  reviewers?
