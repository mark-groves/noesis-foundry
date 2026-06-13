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
PYTHONPATH=src python -m noesis extract evidence --vault examples/noesis-vault --source source-id --title "Evidence Title"
PYTHONPATH=src python -m noesis propose claim --vault examples/noesis-vault --evidence evidence-id --title "Claim Title"
PYTHONPATH=src python -m noesis review approve claim-id --vault examples/noesis-vault --reviewer "Reviewer"
PYTHONPATH=src python -m noesis synthesize --vault examples/noesis-vault --claim claim-id --title "Synthesis Title"
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review approve synthesis-id --vault examples/noesis-vault --reviewer "Reviewer"
PYTHONPATH=src python -m noesis knowledge promote --vault examples/noesis-vault --synthesis synthesis-id --title "Reviewed Knowledge Title"
PYTHONPATH=src python -m noesis memory stale reviewed-knowledge-id --vault examples/noesis-vault --reason "Superseded by newer evidence"
PYTHONPATH=src python -m noesis trace reviewed-knowledge-noesis-lifecycle --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --purpose "prepare the next agent"
PYTHONPATH=src python -m noesis context write --vault examples/noesis-vault --purpose "prepare the next agent"
```

Supported commands:

| Command | Purpose |
| --- | --- |
| `noesis vault doctor <path>` | Report contract compatibility, validation completeness, and CLI/MCP readiness. |
| `noesis vault validate <path>` | Validate required frontmatter, lifecycle stage/status values, wikilinks, Base YAML, Canvas JSON, and active-context exclusions. |
| `noesis vault init <path>` | Create the V1 contract metadata file, folder schema, templates, review dashboard, Base views, Canvas placeholder, and minimal Obsidian settings. |
| `noesis ingest source --vault <path> --file <path> --title <title>` | Copy immutable raw material into `raw/` and create a linked source note in `sources/`. |
| `noesis extract evidence --vault <path> --source <source-id>` | Create a reviewable evidence draft linked back to a source note. |
| `noesis propose claim --vault <path> --evidence <evidence-id>` | Create a review-ready claim draft grounded in one or more evidence notes. |
| `noesis synthesize --vault <path> --claim <claim-id>` | Create a review-ready synthesis draft grounded in claim, evidence, and source links. |
| `noesis review queue --vault <path>` | List notes whose `review_state` still needs attention. |
| `noesis review approve <note-id> --vault <path>` | Write an audit review note and mark the reviewed note approved. |
| `noesis review request-changes <note-id> --vault <path>` | Write an audit review note and keep the reviewed note in the review queue. |
| `noesis knowledge promote --vault <path> --synthesis <synthesis-id>` | Promote an approved synthesis with a review audit into active reviewed knowledge. |
| `noesis memory stale <note-id> --vault <path> --reason <reason>` | Mark memory stale or superseded, create a stale-memory trace note, and update affected context exclusions. |
| `noesis trace <note> --vault <path>` | Print the connected lineage for a note across source, evidence, claim, synthesis, review, knowledge, context, stale memory, and archive history. |
| `noesis context build --vault <path>` | Build a focused operational context package from current reviewed knowledge only, excluding stale, superseded, and archived memory. |
| `noesis context write --vault <path>` | Write an operational context note from current reviewed knowledge. |

The vault files are the source of truth. The CLI and MCP server are implemented
adapters over the same parser, validator, lineage tracer, review queue, context
builder, and lifecycle write functions. Portable Agent Skills remain a future
adapter layer; when added, they should prefer the CLI or MCP tools and fall back
to direct Markdown edits only as adapter behavior. Neither MCP nor skills should
introduce a second schema or make Obsidian plugin APIs the source of truth.

The supported local install smoke path is:

```bash
python -m venv --system-site-packages /tmp/noesis-smoke
/tmp/noesis-smoke/bin/python -m pip install -e .
/tmp/noesis-smoke/bin/noesis vault doctor examples/noesis-vault --json
/tmp/noesis-smoke/bin/noesis-mcp --help
```

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
| `noesis_build_context` | Build operational context from current reviewed knowledge only, excluding stale, superseded, and archived memory. |

Controlled write tools:

| Tool | Purpose |
| --- | --- |
| `noesis_ingest_source` | Copy raw source material into `raw/` and create a linked source note. |
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

---

## Long-Term Aim

Noesis Foundry should become a memory environment where knowledge work compounds.

Every project should become easier to continue.

Every research thread should become easier to deepen.

Every study path should become easier to navigate.

Every development session, human or agentic, should leave the next one better prepared.

Every agent should start from a better place than the agent before it.

Noesis is ultimately a system for turning experience into durable understanding.
