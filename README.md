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

---

## Long-Term Aim

Noesis Foundry should become a memory environment where knowledge work compounds.

Every project should become easier to continue.

Every research thread should become easier to deepen.

Every study path should become easier to navigate.

Every development session, human or agentic, should leave the next one better prepared.

Every agent should start from a better place than the agent before it.

Noesis is ultimately a system for turning experience into durable understanding.
