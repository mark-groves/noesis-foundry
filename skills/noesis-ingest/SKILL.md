---
name: noesis-ingest
description: Add source material to a Noesis vault. Use when a user asks to ingest, capture, import, or preserve research/source material, then create source and evidence drafts while keeping raw files immutable and reviewable.
---

# Noesis Ingest

Use this skill to add new source material to a Noesis vault and prepare
reviewable evidence drafts. The vault contract is defined by the repository
README, `docs/architecture/noesis-local-first-obsidian-interface.md`, and the
`noesis` CLI.

This is a portable Agent Skill for file-backed Noesis vaults. Prefer the
`noesis` CLI and use direct Markdown fallback only when the CLI is unavailable.

## Workflow

1. Identify the vault path and source material. If no vault is named and you are
   in this repository, default to `examples/noesis-vault` only for examples or
   tests; otherwise ask for the target vault. For multiple local files, prefer
   directory ingest or pass the file list in deterministic order.
2. Validate the vault before writing:

   ```bash
   PYTHONPATH=src python -m noesis vault validate <vault>
   ```

   Use `noesis vault validate <vault>` instead when the console script is
   available.
3. Preserve the raw source and create the source note through the CLI:

   ```bash
   PYTHONPATH=src python -m noesis ingest source --vault <vault> --file <source-file> --title "<source title>"
   ```

   Pass optional source metadata such as `--original-url`, `--author`, and
   `--source-date` when the user or source provides it. The CLI records a
   SHA-256 content hash and skips already-captured content unless
   `--allow-duplicates` is set.
4. For batch capture, use directory ingest and request one evidence draft per
   new source when a reviewable placeholder is useful:

   ```bash
   PYTHONPATH=src python -m noesis ingest source --vault <vault> --directory <source-dir> --recursive --evidence-drafts
   ```

   Review the created/skipped summary before doing interpretive work.
5. Extract one or more evidence drafts from a created source note when more
   specific atomic evidence is needed:

   ```bash
   PYTHONPATH=src python -m noesis extract evidence --vault <vault> --source <source-id> --title "<evidence title>" --evidence "<atomic evidence>"
   ```

   Keep each evidence note atomic enough for later claim review.
6. Re-run vault validation and inspect the created notes. Confirm the source
   note links to preserved raw material and evidence drafts link back to the
   source.

## Fallback

Use direct Markdown/YAML only when the CLI or Python module cannot run. In that
case, copy the closest local templates from `<vault>/_templates`, preserve the
raw source under `<vault>/raw`, use flat YAML and wikilinks as described by the
README/docs, and leave new interpretive notes in a reviewable draft state. Do
not invent new required fields or a second schema.

## Reviewability

- Do not overwrite captured raw source files unless the user explicitly asks.
- Do not mark evidence, claims, syntheses, or knowledge as approved during
  ingest.
- Keep generated evidence source-backed and cite the source note with a
  wikilink.
- Report created note IDs, files written, validation results, and any source
  metadata that was unknown.
