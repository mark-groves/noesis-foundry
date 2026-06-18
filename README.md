# noesis-foundry

**Noesis Foundry** is a local-first memory and synthesis system for helping humans and agents build durable understanding across research, projects, study, and development.

It is the implementation home for **Noesis**: a system for turning scattered sources, conversations, decisions, experiments, mistakes, discoveries, and reflections into knowledge that can be trusted, reviewed, reused, and evolved over time.

The full vision is in [`VISION.md`](./VISION.md).

---

## What Noesis Is

Noesis is a human-agent memory system.

It is designed to help people and AI agents carry understanding forward across time, rather than repeatedly rediscovering the same context.

Noesis is built around a simple belief:

> Memory is not accumulation.  
> Useful memory requires structure, review, context, and lifecycle.

The system helps transform raw material into living understanding:

```text
sources → evidence → claims → synthesis → reviewed knowledge → operational context
```

That context can then support future research sessions, project work, study, development, and agentic coding.

---

## Why It Exists

Modern knowledge work produces more material than humans or agents can reliably carry forward.

Notes, documents, transcripts, code changes, tool outputs, decisions, lessons, contradictions, assumptions, and unfinished thoughts often disappear, go stale, or pile up as noise.

Noesis exists to make that material usable.

It helps preserve what matters, expose what is uncertain, identify what has changed, and prevent outdated information from silently guiding future work.

The goal is not just to store information.

The goal is to help knowledge mature.

---

## What Noesis Helps With

Noesis supports memory across several kinds of work.

### Research

Remember sources, claims, open questions, contradictions, emerging concepts, and evolving interpretations.

### Projects

Preserve decisions, assumptions, risks, customer context, rationale, unresolved questions, and handoffs.

### Study

Track learning objectives, weak areas, mistakes, review needs, supporting resources, and mastery over time.

### Development & Agentic Coding

Help humans and coding agents carry forward architecture context, repo conventions, commands, implementation notes, failed attempts, changed assumptions, tool outputs, handoffs, and lessons that would otherwise need to be rediscovered.

These areas should be connected by shared principles, but not flattened into one undifferentiated knowledge base.

---

## Core Idea

Noesis treats memory as a lifecycle.

A useful memory system should be able to distinguish between:

- raw source material
- extracted evidence
- draft interpretation
- source-backed claims
- reviewed understanding
- active operational context
- stale assumptions
- superseded decisions
- archived history

Old information should not disappear without trace, but it should stop shaping active work once it is no longer reliable or useful.

---

## How It Works

At a high level, Noesis turns experience into durable understanding through a recurring cycle:

1. Capture source material.
2. Extract structured evidence.
3. Form claims grounded in that evidence.
4. Combine claims into synthesis.
5. Review, refine, and mature that synthesis.
6. Use reviewed knowledge as focused context for future work.
7. Revisit, revise, supersede, or retire memory as reality changes.

The system should make it clear where knowledge came from, why it matters, how confident it is, and whether it should still be trusted.

---

## Human-Centred Memory

Noesis is not intended to replace human judgement.

The human remains at the centre of meaning, interpretation, and review.

Agents can help maintain memory by extracting evidence, surfacing contradictions, compacting noisy work, preparing context, and proposing updates.

But durable understanding should remain inspectable, traceable, and reviewable by the human.

---

## Local-First Direction

Noesis Foundry begins from a local-first assumption.

Knowledge should be stored in a way that the user can inspect, move, back up, and control.

Future versions may integrate with external tools or services, but the core memory lifecycle should not depend on a remote platform.

---

## Design Commitments

Noesis should be:

- **Source-backed** — durable knowledge should trace back to evidence.
- **Reviewable** — humans should be able to inspect and revise memory.
- **Lifecycle-aware** — memory can become stale, superseded, archived, or retired.
- **Context-conscious** — agents should receive focused context, not everything.
- **Local-first** — the user should control their knowledge environment.
- **Legible** — the system should explain what it remembers and why it matters.
- **Composable** — different knowledge spaces should share principles without becoming one monolith.

---

## Project Status

This repository is in its early formation stage.

The initial aim is to turn the Noesis vision into a working local-first memory system with a practical foundation for:

- capturing sources
- structuring evidence
- grounding claims
- synthesising understanding
- reviewing memory
- managing lifecycle state
- preparing focused context for future work

Implementation details will evolve as the project takes shape.

### Current Prototype

The first local-first Obsidian interface design is documented in
[`docs/architecture/noesis-local-first-obsidian-interface.md`](./docs/architecture/noesis-local-first-obsidian-interface.md).

The plugin and adapter decision is captured in
[`docs/adr/0001-obsidian-stack.md`](./docs/adr/0001-obsidian-stack.md).

A small example vault lives in [`examples/noesis-vault`](./examples/noesis-vault)
and demonstrates the complete Noesis lifecycle from source to operational
context. Initialized V1 vaults also include `noesis.vault.yaml`, a small
root-level compatibility artifact that records the vault contract version
without requiring every note to carry version metadata.

### First CLI Slice

The first working CLI is intentionally file-backed. It treats an Obsidian vault
as ordinary Markdown files with flat YAML frontmatter, plus Obsidian Base and
Canvas files as human-facing views.

Run commands from the repository with `PYTHONPATH=src python -m noesis ...`.
For local console-script use, install the package into a virtual environment
and run `noesis ...` or `noesis-mcp ...` from that environment.

```bash
PYTHONPATH=src python -m noesis vault doctor examples/noesis-vault
PYTHONPATH=src python -m noesis vault validate examples/noesis-vault
PYTHONPATH=src python -m noesis vault init /tmp/noesis-vault
PYTHONPATH=src python -m noesis ingest source --vault examples/noesis-vault --file /path/to/source.md --title "Source Title"
PYTHONPATH=src python -m noesis ingest source --vault examples/noesis-vault --directory /path/to/sources --recursive --evidence-drafts
PYTHONPATH=src python -m noesis ingest bundle --vault examples/noesis-vault /path/to/source-bundle --evidence-drafts
PYTHONPATH=src python -m noesis extract evidence --vault examples/noesis-vault --source source-id --title "Evidence Title"
PYTHONPATH=src python -m noesis propose claim --vault examples/noesis-vault --evidence evidence-id --title "Claim Title"
PYTHONPATH=src python -m noesis review approve claim-id --vault examples/noesis-vault --reviewer "Reviewer"
PYTHONPATH=src python -m noesis synthesize --vault examples/noesis-vault --claim claim-id --title "Synthesis Title"
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault --review-state ready-for-review --due --due-on 2026-06-13
PYTHONPATH=src python -m noesis review summary --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review show claim-id --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review approve synthesis-id --vault examples/noesis-vault --reviewer "Reviewer"
PYTHONPATH=src python -m noesis knowledge promote --vault examples/noesis-vault --synthesis synthesis-id --title "Reviewed Knowledge Title"
PYTHONPATH=src python -m noesis memory stale reviewed-knowledge-id --vault examples/noesis-vault --reason "Superseded by newer evidence"
PYTHONPATH=src python -m noesis trace reviewed-knowledge-noesis-lifecycle --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --purpose "prepare the next agent"
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope agent-memory --limit 1 --purpose "prepare the next agent"
PYTHONPATH=src python -m noesis context explain --vault examples/noesis-vault --scope agent-memory
PYTHONPATH=src python -m noesis context write --vault examples/noesis-vault --purpose "prepare the next agent"
```

Supported commands:

| Command | Purpose |
| --- | --- |
| `noesis vault doctor <path>` | Report contract compatibility, validation completeness, and CLI/MCP readiness. |
| `noesis vault validate <path>` | Validate required frontmatter, lifecycle stage/status values, wikilinks, Base YAML, Canvas JSON, and active-context exclusions. |
| `noesis vault init <path>` | Create the V1 contract metadata file, folder schema, templates, review dashboard, Base views, Canvas placeholder, and minimal Obsidian settings. |
| `noesis ingest source --vault <path> --file <path> --title <title>` | Copy immutable raw material into `raw/`, add source provenance and a SHA-256 content hash, skip already-captured content unless `--allow-duplicates` is set, and create a linked source note in `sources/`. |
| `noesis ingest source --vault <path> --directory <path> --recursive --evidence-drafts` | Import local source files in deterministic path order, report created/skipped summaries, and optionally create one reviewable evidence draft for each new source. |
| `noesis ingest bundle --vault <path> <bundle-path> --evidence-drafts` | Import a local manifest-driven artifact bundle in deterministic artifact-path order, preserve raw artifacts, record bundle provenance, skip duplicate content, and optionally create reviewable evidence drafts. |
| `noesis extract evidence --vault <path> --source <source-id>` | Create a reviewable evidence draft linked back to a source note. |
| `noesis propose claim --vault <path> --evidence <evidence-id>` | Create a review-ready claim draft grounded in one or more evidence notes. |
| `noesis synthesize --vault <path> --claim <claim-id>` | Create a review-ready synthesis draft grounded in claim, evidence, and source links. |
| `noesis review queue --vault <path>` | List notes whose `review_state` still needs attention, with optional `--review-state`, `--type`, `--stage`, `--due`, and `--due-on` filters. |
| `noesis review summary --vault <path>` | Summarize review-state counts, pending items, due reviews, and upcoming `next_review` dates. |
| `noesis review show <note-id> --vault <path>` | Inspect one note's current state, support links, audit records, requested changes, dependent reviewed knowledge/context impact, and lineage. |
| `noesis review approve <note-id> --vault <path>` | Write an audit review note and mark the reviewed note approved. |
| `noesis review request-changes <note-id> --vault <path>` | Write an audit review note and keep the reviewed note in the review queue. |
| `noesis knowledge promote --vault <path> --synthesis <synthesis-id>` | Promote an approved synthesis with a review audit into active reviewed knowledge. |
| `noesis memory stale <note-id> --vault <path> --reason <reason>` | Mark memory stale or superseded, create a stale-memory trace note, and update affected context exclusions. |
| `noesis trace <note> --vault <path>` | Print the connected lineage for a note across source, evidence, claim, synthesis, review, knowledge, context, stale memory, and archive history. |
| `noesis context build --vault <path>` | Build a focused operational context package from current reviewed knowledge only, excluding stale, superseded, and archived memory. Supports `--scope`, `--purpose`, `--profile agent-handoff`, `--limit`, `--max-chars`, and `--json` for agent-sized packages. |
| `noesis context explain --vault <path>` | Explain which current reviewed knowledge was included, scoped out, or budgeted out, and list stale/superseded/archive notes as background provenance only. |
| `noesis context write --vault <path>` | Write an operational context note from current reviewed knowledge, using the same scope and budget controls as `context build`. |

The vault files are the source of truth. The CLI, MCP server, and repo-local
portable Agent Skills are adapters over the same parser, validator, lineage
tracer, review queue, context builder, and lifecycle write functions. Skills
should prefer the CLI or MCP tools and fall back to direct Markdown edits only
as adapter behavior. Neither MCP nor skills should introduce a second schema or
make Obsidian plugin APIs the source of truth.

The supported local install smoke path is:

```bash
python -m venv /tmp/noesis-smoke
/tmp/noesis-smoke/bin/python -m pip install -e .
/tmp/noesis-smoke/bin/noesis vault doctor examples/noesis-vault --json
/tmp/noesis-smoke/bin/noesis vault validate examples/noesis-vault
/tmp/noesis-smoke/bin/noesis-mcp --help
```

For a fresh install path that does not rely on `PYTHONPATH=src`, see
[`docs/install.md`](./docs/install.md) or run:

```bash
bash scripts/smoke-install.sh
```

The install guide also includes a generic MCP stdio client snippet at
[`examples/mcp/noesis-mcp.example.json`](./examples/mcp/noesis-mcp.example.json).

### Portable Agent Skills

Repo-local portable skills live in [`skills`](./skills):

| Skill | Purpose |
| --- | --- |
| [`noesis-ingest`](./skills/noesis-ingest/SKILL.md) | Add source material, preserve raw files, and create evidence drafts. |
| [`noesis-claim-review`](./skills/noesis-claim-review/SKILL.md) | Review draft memory, write audit notes, approve supported memory, or request changes. |
| [`noesis-context`](./skills/noesis-context/SKILL.md) | Build or write focused operational context from current reviewed knowledge. |

The skills are documentation adapters over the same file-backed contract as the
CLI and MCP server. They point agents back to this README, the architecture
docs, and the CLI instead of duplicating the canonical schema.

For a concrete project-memory dogfood fixture, inspect the agent-memory chain in
the example vault:

```bash
PYTHONPATH=src python -m noesis trace reviewed-knowledge-agent-memory-dogfood --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope agent-memory --purpose "continue Noesis Foundry project work"
```

That fixture starts with local project-session source material in
`examples/noesis-vault/raw/2026-06-13-agent-memory-session.md`, moves through
source, evidence, claim, review, synthesis, and reviewed knowledge notes, and
ends at `context/operational-context-agent-memory-dogfood.md`. It also keeps
`stale/stale-agent-memory-global-summary.md` traceable but excluded from active
context.

### MCP MVP

The MCP server is an implemented adapter layer over the same vault contract. It
does not require Obsidian to be running, and it does not introduce a database,
custom Obsidian plugin, or second schema.

Run the stdio server from the repository with:

```bash
PYTHONPATH=src python -m noesis.mcp_server examples/noesis-vault
```

After installing the package, the equivalent console script is:

```bash
noesis-mcp examples/noesis-vault
```

The server defaults to `examples/noesis-vault` when no vault path is provided.
Tools also accept an optional `vault_path` argument so one server can operate
on another compatible vault when an MCP client passes the path explicitly.

Read tools:

| Tool | Purpose |
| --- | --- |
| `noesis_lint_vault` | Validate folder structure, flat YAML frontmatter, lifecycle values, wikilinks, Bases, Canvases, and context exclusions. |
| `noesis_search_notes` | Search notes by text with optional `type`, lifecycle, status, review state, and limit filters. |
| `noesis_get_note` | Return one parsed note by `noesis_id`, filename stem, path, alias, or wikilink target. |
| `noesis_get_review_queue` | Return notes whose `review_state` still needs attention. |
| `noesis_trace_lineage` | Return connected source, evidence, claim, synthesis, review, knowledge, context, and stale-memory lineage. |
| `noesis_build_context` | Build operational context from current reviewed knowledge only, excluding stale, superseded, and archived memory, with optional scope and budget controls plus selection provenance. Use `profile: "agent-handoff"` for harness-agnostic handoff packs; `codex-handoff` is the Codex dogfood adapter over the same Markdown/YAML contract. |

Controlled write tools:

| Tool | Purpose |
| --- | --- |
| `noesis_ingest_source` | Copy raw source material into `raw/` and create a linked source note. |
| `noesis_import_source_bundle` | Import a local manifest-driven artifact bundle into source notes and optional evidence drafts. |
| `noesis_create_evidence_draft` | Create a reviewable evidence draft linked to a source note. |
| `noesis_create_claim_draft` | Create a review-ready claim draft grounded in evidence notes. |
| `noesis_create_synthesis_draft` | Create a review-ready synthesis draft grounded in claim lineage. |
| `noesis_approve_review` | Write an audit review note and mark the reviewed note approved. |
| `noesis_request_review_changes` | Write an audit review note, request changes, and keep affected memory out of active context where needed. |
| `noesis_promote_synthesis` | Promote an approved synthesis with review audit into active reviewed knowledge. |
| `noesis_mark_memory_stale` | Mark memory stale or superseded and update affected context exclusions. |
| `noesis_write_context` | Write an operational context note from current reviewed knowledge. |

Resources:

| Resource | Purpose |
| --- | --- |
| `noesis://vault/summary` | Compact summary of the default vault. |
| `noesis://note/{note}` | Parsed note from the default vault. |

Write safety is intentionally narrow. MCP write tools call the same lifecycle
functions in `src/noesis/vault.py` as the CLI, validate the vault before writes
where the underlying workflow requires it, roll back failed note writes, and
return structured objects such as `{ "ok": false, "error": "...", "issues": [...] }`
instead of scraping CLI text.

Example agent workflow:

```text
1. Call noesis_lint_vault.
2. Call noesis_get_review_queue to find draft memory.
3. Call noesis_get_note and noesis_trace_lineage before making a review decision.
4. Call noesis_approve_review or noesis_request_review_changes to create an audit note.
5. Call noesis_build_context to prepare current reviewed context for the next task.
```

For an ingest-to-context project workflow, an agent thread should use MCP tools
in the same order as the CLI lifecycle:

```text
1. noesis_lint_vault with the target vault path.
2. noesis_ingest_source for the local source artifact.
3. noesis_create_evidence_draft for atomic source-backed evidence.
4. noesis_create_claim_draft for a narrow claim grounded in that evidence.
5. noesis_create_synthesis_draft when the claim should become durable memory.
6. noesis_get_note and noesis_trace_lineage before review.
7. noesis_approve_review or noesis_request_review_changes to leave an audit trail.
8. noesis_promote_synthesis only after review approval.
9. noesis_build_context or noesis_write_context for the next project task.
```

Use the skill packages when an agent runtime supports portable skills and MCP is
not wired into the thread. The skills should still drive the same CLI or MCP
operations first, and only use direct Markdown fallback when those adapters are
unavailable.

---

## Long-Term Aim

Noesis Foundry should become a memory environment where knowledge work compounds.

Every project should become easier to continue.

Every research thread should become easier to deepen.

Every study path should become easier to navigate.

Every development session, human or agentic, should leave the next one better prepared.

Every agent should start from a better place than the agent before it.

Noesis is ultimately a system for turning experience into durable understanding.
