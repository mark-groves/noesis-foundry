# Noesis Portable Agent Skills

This directory contains repo-local Agent Skills for working with Noesis vaults.
Each skill is portable: the skill package is a directory containing `SKILL.md`
with YAML frontmatter and operating instructions.

The skills are adapters over the existing vault contract. They do not define a
second schema. Agents should use the repository README, architecture docs, and
the `noesis` CLI as the source of truth for commands and file behavior.

## Skills

| Skill | Use when |
| --- | --- |
| [`noesis-ingest`](./noesis-ingest/SKILL.md) | Adding new source material and evidence drafts to a Noesis vault. |
| [`noesis-claim-review`](./noesis-claim-review/SKILL.md) | Reviewing, approving, or requesting changes to draft Noesis memory. |
| [`noesis-context`](./noesis-context/SKILL.md) | Preparing focused operational context for an agent task. |

## Operating Boundary

Prefer the installed CLI whenever it is available:

```bash
noesis vault validate /absolute/path/to/noesis-vault
```

From a source checkout without installation, `PYTHONPATH=src python -m noesis`
is equivalent for local development. Direct Markdown/YAML edits are fallback
adapter behavior only. When falling back, copy local vault templates where
possible, keep YAML flat, use wikilinks for relationships, preserve raw
sources, and validate the vault before reporting completion.

See the root [`README.md`](../README.md),
[`docs/install.md`](../docs/install.md), and
[`docs/architecture/noesis-local-first-obsidian-interface.md`](../docs/architecture/noesis-local-first-obsidian-interface.md)
for the current vault and CLI contract.

## Dogfood Fixture

The example vault includes a Noesis Foundry project-memory fixture:

```bash
PYTHONPATH=src python -m noesis trace reviewed-knowledge-agent-memory-dogfood --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope agent-memory --purpose "continue Noesis Foundry project work"
PYTHONPATH=src python -m noesis trace reviewed-knowledge-noesis-roadmap-phase-orchestration --vault examples/noesis-vault
PYTHONPATH=src python -m noesis context build --vault examples/noesis-vault --scope noesis-roadmap --purpose "orchestrate next Noesis phases"
```

This fixture shows the intended adapter flow without creating a second schema:
local project-session source material is captured, evidence and claims are
reviewed, a synthesis is promoted, stale shortcut memory is preserved, and
operational context is built from reviewed knowledge only. The roadmap slice
uses the same lifecycle to turn checked-in project docs into source-backed
phase-orchestration guidance for future Noesis work.
