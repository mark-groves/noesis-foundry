---
name: noesis-context
description: Prepare focused Noesis context for an agent task. Use when a user asks to build, write, refresh, or inspect operational context from reviewed knowledge while excluding stale, superseded, or unreviewed memory.
---

# Noesis Context

Use this skill to prepare operational context for an agent task from current
reviewed Noesis knowledge. The vault contract is defined by the repository
README, `docs/architecture/noesis-local-first-obsidian-interface.md`, and the
`noesis` CLI.

This is a portable Agent Skill for file-backed Noesis vaults. Prefer the
`noesis` CLI and use direct Markdown fallback only when the CLI is unavailable.

## Workflow

1. Identify the vault, task purpose, and optional scope. Keep the requested task
   narrow enough that the output is useful context, not a vault dump.
2. Validate the vault:

   ```bash
   PYTHONPATH=src python -m noesis vault validate <vault>
   ```

3. Build context from reviewed knowledge only:

   ```bash
   PYTHONPATH=src python -m noesis context build --vault <vault> --purpose "<agent task>" --scope "<optional scope>"
   ```

   Use `--output <path>` when the user wants a separate context artifact.
4. If the task requires a durable operational-context note, write it through the
   CLI:

   ```bash
   PYTHONPATH=src python -m noesis context write --vault <vault> --purpose "<agent task>" --scope "<optional scope>" --title "<context title>"
   ```

5. Trace any included knowledge that seems stale, surprising, or central to the
   task:

   ```bash
   PYTHONPATH=src python -m noesis trace <reviewed-knowledge-id> --vault <vault>
   ```

6. Re-run validation after writing a context note. Report the context output or
   note ID, included reviewed knowledge, excluded stale/superseded memory, and
   any assumptions about scope.

## Fallback

Use direct Markdown/YAML only when the CLI or Python module cannot run. Read
notes under `knowledge/` and exclude notes marked stale, superseded, archived,
unreviewed, or changes-requested according to the README/docs. If writing a
context note, copy the closest local template from `<vault>/_templates`, keep
relationships as wikilinks, and make the exclusions visible to future reviewers.
Do not include raw drafts or unreviewed claims as active guidance.

## Reviewability

- Prefer concise context tailored to the named task over broad summaries.
- Include provenance links so the next agent can trace claims back through
  reviewed knowledge and sources.
- If validation fails, do not prepare authoritative context until the blocker is
  reported or fixed.
- Do not silently revive stale or superseded memory; mention it only as
  excluded background when relevant.
