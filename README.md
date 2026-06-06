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
context.

### First CLI Slice

The first working CLI is intentionally file-backed. It treats an Obsidian vault
as ordinary Markdown files with flat YAML frontmatter, plus Obsidian Base and
Canvas files as human-facing views.

Run commands from the repository with `PYTHONPATH=src python -m noesis ...`, or
install the package in editable mode to use the `noesis` console script.

```bash
PYTHONPATH=src python -m noesis vault validate examples/noesis-vault
PYTHONPATH=src python -m noesis vault init /tmp/noesis-vault
PYTHONPATH=src python -m noesis ingest source --vault examples/noesis-vault --file /path/to/source.md --title "Source Title"
PYTHONPATH=src python -m noesis extract evidence --vault examples/noesis-vault --source source-id --title "Evidence Title"
PYTHONPATH=src python -m noesis propose claim --vault examples/noesis-vault --evidence evidence-id --title "Claim Title"
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
| `noesis vault validate <path>` | Validate required frontmatter, lifecycle stage/status values, wikilinks, Base YAML, Canvas JSON, and active-context exclusions. |
| `noesis vault init <path>` | Create the folder schema, templates, review dashboard, Base views, Canvas placeholder, and minimal Obsidian settings. |
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

The CLI is the shared implementation foundation for future adapters. A future
MCP server should expose curated tools that call the same parser, validator,
lineage tracer, review queue, and context builder. Portable Agent Skills should
prefer these commands when available and fall back to direct Markdown edits
only as an adapter behavior. Neither MCP nor skills should introduce a second
schema or make Obsidian plugin APIs the source of truth.

---

## Long-Term Aim

Noesis Foundry should become a memory environment where knowledge work compounds.

Every project should become easier to continue.

Every research thread should become easier to deepen.

Every study path should become easier to navigate.

Every development session, human or agentic, should leave the next one better prepared.

Every agent should start from a better place than the agent before it.

Noesis is ultimately a system for turning experience into durable understanding.
