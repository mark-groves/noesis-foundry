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

Prefer the CLI whenever it is available:

```bash
PYTHONPATH=src python -m noesis vault validate examples/noesis-vault
```

If the package is installed, the `noesis` console script is equivalent. Direct
Markdown/YAML edits are fallback adapter behavior only. When falling back, copy
local vault templates where possible, keep YAML flat, use wikilinks for
relationships, preserve raw sources, and validate the vault before reporting
completion.

See the root [`README.md`](../README.md) and
[`docs/architecture/noesis-local-first-obsidian-interface.md`](../docs/architecture/noesis-local-first-obsidian-interface.md)
for the current vault and CLI contract.
