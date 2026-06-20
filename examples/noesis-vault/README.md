# Noesis Example Vault

This is a small Obsidian-compatible vault demonstrating one complete Noesis
lifecycle:

```text
source -> evidence -> claim -> synthesis -> reviewed knowledge -> operational context
```

It also includes a second minimal `source -> evidence -> claim` chain created
by the write-side CLI commands. That fixture starts at
`sources/source-cli-authoring-loop.md` and proves the CLI can author new
source-backed draft memory outside the original hand-written demo.

The ingest command can also capture a directory of local source files in
deterministic path order. New source notes record optional provenance fields
such as `source_type`, `original_url`, `author`, `source_date`, `captured`,
`content_hash`, `source_size_bytes`, and `original_path`; duplicate content is
skipped by default and reported in the command summary.

For realistic project artifact imports, `ingest bundle` reads a local
`noesis-bundle.yaml` manifest and captures listed artifacts in deterministic
artifact-path order. The test fixture at
`tests/fixtures/codex-session-bundle` demonstrates a Codex session export
without requiring network access; imported source notes add flat bundle
metadata such as `bundle_schema_version`, `bundle_id`,
`bundle_artifact_path`, `bundle_artifact_hash`, `bundle_manifest_hash`, and
`bundle_item_index`. The v1 manifest contract is documented in
`docs/source-bundle-schema-v1.md`.

The `agent-memory` dogfood extension models a realistic project-session handoff:
`source -> evidence -> claim -> review -> synthesis -> reviewed knowledge ->
operational context`. It starts at `sources/source-agent-memory-session.md`,
ends at `context/operational-context-agent-memory-dogfood.md`, and keeps
`stale/stale-agent-memory-global-summary.md` traceable but excluded from
generated context.

The `noesis-roadmap` project-memory extension uses the checked-in README,
architecture, and skill docs as source material for next-phase planning. It
starts at `sources/source-noesis-roadmap-docs.md`, promotes
`knowledge/reviewed-knowledge-noesis-roadmap-phase-orchestration.md`, ends at
`context/operational-context-noesis-roadmap-phase-orchestration.md`, and keeps
`stale/stale-noesis-roadmap-plugin-first.md` traceable but excluded from active
roadmap guidance.

The `project-memory-corpus` continuation extension is a larger multi-source
chain for future agents expanding this repository's own memory. It starts from
checked-in repo artifacts, checked-in review governance examples, and a local
session bundle fixture at `sources/source-project-memory-corpus-repo-artifacts.md`,
`sources/source-project-memory-corpus-bundle-fixture.md`, and
`sources/source-project-memory-corpus-review-governance.md`, promotes
`knowledge/reviewed-knowledge-project-memory-corpus-continuation.md`, ends at
`context/operational-context-project-memory-corpus-continuation.md`, keeps
`stale/stale-project-memory-corpus-bulk-import-active-context.md` traceable but
excluded from active context, and preserves
`evidence/evidence-project-memory-corpus-unreviewed-import-draft.md` as a
review-queued input that must not bypass promotion.

The `gaps/knowledge-gap-noesis-roadmap-plugin-tension.md` fixture demonstrates
a source-backed contradiction gap. It links current roadmap source/evidence and
claims to the stale plugin-first assumption so users and agents can inspect why
the tension exists without loading stale memory into active context.

The checked-in fixture now demonstrates scoped memory spaces without making
space metadata mandatory. `reviewed-knowledge-agent-memory-dogfood.md` and its
context package use `memory_space: noesis-foundry-codebase` with
`memory_domain: codebase`. The roadmap and project-memory-corpus context use
`memory_space: noesis-foundry-project` with `memory_domain: project`. Older
notes without those fields remain valid default memory and continue to appear
when no memory-space filter is requested.

The CLI context composer can scope and budget the active package without
weakening lifecycle safety:

```bash
PYTHONPATH=src python -m noesis vault spaces examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope agent-memory --limit 1 --purpose "prepare a future agent"
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --memory-domain codebase --scope agent-memory
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope noesis-roadmap --purpose "orchestrate next Noesis phases"
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope noesis-roadmap --purpose "orchestrate next Noesis phases" --profile agent-handoff
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope noesis-roadmap --purpose "orchestrate next Noesis phases" --profile codex-handoff
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope project-memory-corpus --purpose "continue expanding Noesis Foundry project memory"
PYTHONPATH=src python -m noesis context explain --vault examples/noesis-vault --memory-space noesis-foundry-project
PYTHONPATH=src python -m noesis context explain --vault examples/noesis-vault --scope agent-memory
PYTHONPATH=src python -m noesis knowledge gaps --vault examples/noesis-vault
```

`context build` prints active guidance from current reviewed knowledge only.
`context explain` shows why reviewed notes were included, scoped out, or
budgeted out, and labels stale/superseded/archive notes as background
provenance only.
`knowledge gaps` reports open questions, weak areas, and contradictions from
source-backed gap notes without adding them to active context.

Use `--profile agent-handoff` when launching parallel work in any capable agent
harness. That profile renders a handoff pack with the task purpose, selected
reviewed knowledge, scoped-out reviewed knowledge, selection provenance,
relevant lineage, lifecycle exclusions, assumptions, validation commands, and
next-step guidance. `--profile codex-handoff` is the Codex dogfood adapter for
the same Noesis handoff boundary, not a separate product contract. Excluded
stale, superseded, and archived notes appear by identifier and lifecycle reason
only; their bodies are not active guidance.

For a Codex or agent thread working on this repository, the fixture can be
checked with:

```bash
PYTHONPATH=src python -m noesis trace reviewed-knowledge-agent-memory-dogfood --vault examples/noesis-vault
PYTHONPATH=src python -m noesis trace reviewed-knowledge-noesis-roadmap-phase-orchestration --vault examples/noesis-vault
PYTHONPATH=src python -m noesis trace reviewed-knowledge-project-memory-corpus-continuation --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope agent-memory --purpose "continue Noesis Foundry project work"
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope noesis-roadmap --purpose "orchestrate next Noesis phases" --profile agent-handoff
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope project-memory-corpus --purpose "continue expanding Noesis Foundry project memory"
```

An MCP client should follow the same lifecycle through `noesis_ingest_source`
or `noesis_import_source_bundle`, `noesis_create_evidence_draft`,
`noesis_create_claim_draft`, review tools, and `noesis_build_context`; the
tools are adapters over these vault files, not a separate source of truth.

Open this folder as a vault in Obsidian, then start at
`_dashboards/noesis-review-dashboard.md`. The dashboard is the human workbench
for four review questions: what supports this memory, when should it be
reviewed again, which reviewed knowledge feeds active context, and which stale
or superseded provenance must remain visible without guiding current work.

The durable source of truth is Markdown plus YAML properties. The `_bases`,
`_canvas`, and `_dashboards` folders are human views over those notes.

## Important Files

- `_dashboards/noesis-review-dashboard.md` - human review workbench entry
  point.
- `_bases/review-queue.base` - Base views for notes needing review and
  scheduled `next_review` dates.
- `_bases/lifecycle-dashboard.base` - Base views grouped by lifecycle and
  status, including active trusted context candidates and stale/superseded
  lifecycle exceptions.
- `_bases/traceability-workbench.base` - Base views for lineage links, review
  audit records, trust review schedules, context inclusion/exclusion, and
  knowledge gaps, active context, and excluded or superseded memory.
- `_canvas/noesis-lifecycle.canvas` - visual map of the example lifecycle and
  human workbench views.
- `_templates/` - note templates for humans and agents.
- `context/operational-context-first-cli-mcp-workflow.md` - the final context
  package the next agent would read.
- `context/operational-context-agent-memory-dogfood.md` - a scoped dogfood
  context package for agent-memory work.
- `context/operational-context-noesis-roadmap-phase-orchestration.md` - a
  scoped context package for next-phase Noesis roadmap work.
- `context/operational-context-project-memory-corpus-continuation.md` - a
  scoped continuation package for expanding the project-memory corpus.
- `gaps/knowledge-gap-noesis-roadmap-plugin-tension.md` - a source-backed
  contradiction gap that remains reportable but excluded from active context.

The CLI review workbench mirrors the Obsidian view without becoming canonical
storage:

```bash
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --memory-domain codebase
PYTHONPATH=src python -m noesis review show stale-custom-plugin-first --vault examples/noesis-vault
PYTHONPATH=src python -m noesis knowledge gaps --vault examples/noesis-vault
```

Use `review summary` and `review queue` to triage overdue scheduled reviews,
requested changes, audit gaps, and downstream impact counts. Use `review show`
before approving, renewing, or requesting changes when you need the note's
lineage, evidence support, audit trail, downstream context impact, and changes
requested in one place. Renewing stale or superseded memory records a review
audit and reschedules the note without making it active context again.
The Direct audit link checks Base view is a frontmatter shortcut; the CLI
review summary is the canonical audit-gap check because review notes can also
link reviewed targets through `reviewed_notes`.

Template note: Obsidian core Templates will replace `{{title}}` and `{{date}}`.
Placeholders in angle brackets, such as `<slug>`, are for humans, the future
CLI, or agent skills to fill.
