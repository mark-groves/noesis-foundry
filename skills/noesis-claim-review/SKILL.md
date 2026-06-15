---
name: noesis-claim-review
description: Review or mature Noesis memory. Use when a user asks to inspect draft claims, evidence, syntheses, or reviewed knowledge, approve supported memory, request changes, or preserve a review audit trail.
---

# Noesis Claim Review

Use this skill to review Noesis memory without bypassing provenance or the
human-inspectable audit trail. The vault contract is defined by the repository
README, `docs/architecture/noesis-local-first-obsidian-interface.md`, and the
`noesis` CLI.

This is a portable Agent Skill for file-backed Noesis vaults. Prefer the
`noesis` CLI and use direct Markdown fallback only when the CLI is unavailable.

## Workflow

1. Validate the vault before making a review decision:

   ```bash
   PYTHONPATH=src python -m noesis vault validate <vault>
   ```

2. Find reviewable notes:

   ```bash
   PYTHONPATH=src python -m noesis review queue --vault <vault>
   ```

3. For each note under review, read the note and trace its lineage before
   deciding:

   ```bash
   PYTHONPATH=src python -m noesis trace <note-id> --vault <vault>
   ```

   Inspect the linked source, evidence, claims, synthesis, existing review
   notes, stale notes, and active context that may depend on the memory.
4. Approve only when the note is grounded in its linked evidence and does not
   conflict with current reviewed knowledge:

   ```bash
   PYTHONPATH=src python -m noesis review approve <note-id> --vault <vault> --reviewer "<reviewer>" --basis "<why this is supported>"
   ```

5. Request changes when support is missing, lineage is broken, wording is too
   broad, or the note conflicts with fresher knowledge:

   ```bash
   PYTHONPATH=src python -m noesis review request-changes <note-id> --vault <vault> --reviewer "<reviewer>" --changes-requested "<specific change>"
   ```

6. Promote or stale memory only through the CLI when the task explicitly asks
   to mature or retire memory:

   ```bash
   PYTHONPATH=src python -m noesis knowledge promote --vault <vault> --synthesis <synthesis-id> --title "<knowledge title>"
   PYTHONPATH=src python -m noesis memory stale <note-id> --vault <vault> --reason "<reason>"
   ```

7. Re-run validation and the review queue. Report the review note created, the
   reviewed note's final state, and remaining queue items.

## Concrete Example

The example vault has an approved Noesis Foundry project-memory chain. Use it
as the review shape before approving new memory:

```bash
PYTHONPATH=src python -m noesis trace claim-agent-memory-dogfood --vault examples/noesis-vault
PYTHONPATH=src python -m noesis review queue --vault examples/noesis-vault
```

The equivalent MCP path is `noesis_get_note`, `noesis_trace_lineage`, and then
either `noesis_approve_review` or `noesis_request_review_changes`. After an
approval, use `noesis_promote_synthesis` only for an approved synthesis with a
review audit.

## Fallback

Use direct Markdown/YAML only when the CLI or Python module cannot run. In that
case, copy the review template from `<vault>/_templates`, write an explicit
review note in `review/`, update the reviewed note only as far as the README and
architecture docs require, and keep all relationships as wikilinks. Do not mark
memory approved without an audit review note.

## Reviewability

- Never approve a note just because it is well-written; check source and
  evidence lineage.
- Preserve disagreement by requesting changes or creating follow-up review
  notes instead of deleting uncertain memory.
- Keep stale or superseded memory traceable; do not remove it from the vault as
  part of review.
- If validation fails before review, report the blocker and avoid state changes.
