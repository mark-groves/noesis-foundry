# Project Memory Corpus Bundle Fixture Source

Captured: 2026-06-18

This raw source captures the local `tests/fixtures/codex-session-bundle`
artifact bundle as evidence for how Noesis should preserve project-session
material before review.

## Fixture Artifacts

- `tests/fixtures/codex-session-bundle/noesis-bundle.yaml` declares a Codex
  session export with deterministic artifact entries.
- The bundle manifest includes a transcript artifact whose evidence text says
  the transcript records a request to build a Noesis capture/import pipeline
  from local project artifacts.
- The bundle manifest includes a metadata artifact whose evidence text says the
  metadata identifies the delegated Codex session and branch used for import
  pipeline work.
- `exports/02-transcript.md` says the import path must preserve local raw
  artifacts, record provenance, and create reviewable evidence drafts without
  requiring live network access.
- `exports/03-transcript-copy.md` intentionally duplicates the transcript
  content, demonstrating that duplicate source material should be preserved or
  skipped deterministically rather than silently becoming additional active
  context.

## Interpretation Boundary

The fixture supports importing and reviewing local project-session artifacts as
source-backed memory. It does not support promoting every captured artifact
directly into active context.
