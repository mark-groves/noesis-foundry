# Source Bundle Schema V1

Source bundles import local project artifacts into a Noesis vault through a
single manifest file named `noesis-bundle.yaml` by default. The importer is a
thin adapter over the vault contract: it copies immutable raw artifacts into
`raw/`, creates source notes in `sources/`, records flat YAML metadata, and can
optionally create one reviewable evidence draft per newly created source.

## Manifest

The manifest is a YAML mapping. New bundles should set `schema_version: 1`;
manifests without `schema_version` are treated as v1 for compatibility.

Required top-level fields:

- `artifacts` - non-empty list of artifact path strings or artifact mappings.

Optional top-level fields:

- `schema_version` - source bundle schema version. Only `1` is supported.
- `bundle_id` - stable bundle identifier. Defaults to the bundle title.
- `title` - human title for the bundle. Defaults from the bundle folder name.
- `source_type` - default source type for artifacts.
- `original_url` - default upstream URL or identifier.
- `author` - default artifact author.
- `source_date` - default source date as `YYYY-MM-DD` or `unknown`.

Accepted artifact fields:

- `path` - required path to a file inside the bundle directory.
- `id` - stable artifact identifier. Defaults from the artifact slug.
- `title` - source note title. Defaults from the artifact path.
- `slug` - source note slug. Defaults from the artifact path.
- `source_type` - overrides the bundle-level source type.
- `original_url` - overrides the bundle-level URL or identifier.
- `author` - overrides the bundle-level author.
- `source_date` - overrides the bundle-level date.
- `evidence_title` - optional evidence draft title.
- `evidence` - optional evidence draft body text.
- `evidence_slug` - optional evidence draft slug.

All manifest fields must be scalar values except `artifacts`. Unknown fields,
nested mappings, nested lists, absolute paths, `..` paths, missing files,
duplicate artifact paths, duplicate artifact IDs, and unsupported schema
versions are rejected before any raw artifact or source note is written.

## Import Order And Duplicates

Artifacts are imported in deterministic artifact-path order, not manifest order.
The created source metadata records both `bundle_item_index`, which is the
deterministic import position, and `bundle_manifest_index`, which is the
original 1-based manifest position.

Content duplicates are skipped by default using SHA-256 source hashes. This
allows a bundle to contain distinct artifact paths with identical content while
preserving a deterministic skipped result. Use `--allow-duplicates` only when
you intentionally want duplicate content captured as new source notes.

## Source Metadata

Imported source notes retain the regular source fields such as `source_type`,
`raw_path`, `original_url`, `author`, `source_date`, `content_hash`,
`content_hash_algorithm`, `source_size_bytes`, and `original_path`.

Bundle imports also add these flat YAML fields:

- `import_pipeline: source-bundle`
- `bundle_schema: noesis-source-bundle`
- `bundle_schema_version`
- `bundle_id`
- `bundle_title`
- `bundle_path`
- `bundle_manifest_path`
- `bundle_manifest_hash`
- `bundle_artifact_path`
- `bundle_artifact_hash`
- `bundle_artifact_size_bytes`
- `bundle_item_id`
- `bundle_item_index`
- `bundle_manifest_index`

## Example

```yaml
schema_version: 1
bundle_id: codex-session-export-demo
title: Codex Session Export Demo
source_type: codex-session-export
original_url: codex-session://019ec917-cf18-7033-92b8-02183947995e
author: Codex Test Fixture
source_date: 2026-06-15
artifacts:
  - path: exports/01-session.json
    id: session-metadata
    title: Codex Session Metadata
    slug: codex-session-metadata
    source_type: codex-session-metadata
    evidence_title: Session Metadata Evidence
    evidence_slug: session-metadata
    evidence: The metadata identifies the delegated Codex session.
  - path: exports/02-transcript.md
    id: session-transcript
    title: Codex Session Transcript
    slug: codex-session-transcript
```

Import with evidence drafts and structured output:

```bash
PYTHONPATH=src python -m noesis ingest bundle --vault <vault> <bundle> --evidence-drafts --json
```
