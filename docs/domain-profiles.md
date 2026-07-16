# Domain Profiles

Noesis keeps one source-backed lifecycle while allowing different kinds of
work to ask for different context shapes. Profiles tune selection budgets and
rendering; they do not create another schema or bypass review.

| Profile | Best used for | Default emphasis |
| --- | --- | --- |
| `coding` | Continuing implementation or debugging | Architecture, commands, traps, changed assumptions, decisions, and handoffs; 6 notes / 14,000 selected body characters. |
| `project-continuation` | Resuming broader project work | Decisions, assumptions, risks, unresolved questions, rationale, and current state; 8 notes / 16,000 characters. |
| `research` | Deepening a research thread | Source-backed claims, evidence boundaries, tensions, contradictions, and open questions; 10 notes / 24,000 characters. |
| `study` | Planning or resuming study | Objectives, weak areas, prior mistakes, resources, mastery state, and scheduled review; 8 notes / 18,000 characters. |
| `review` | Evaluating lifecycle changes | A narrow support, audit, freshness, and downstream-impact view; 6 notes / 12,000 characters. |
| `agent-handoff` | Starting another agent thread | Harness-neutral task purpose, active guidance, lineage, assumptions, validation commands, and next steps. |
| `codex-handoff` | Dogfooding a coding-agent handoff | The same handoff contract with Codex-oriented framing; it is an adapter, not a separate memory model. |

Example:

```bash
noesis context build \
  --vault /path/to/vault \
  --profile coding \
  --scope "authentication architecture" \
  --purpose "continue the implementation" \
  --as-of 2026-07-16 \
  --freshness-policy strict \
  --json
```

`next_review` and `valid_until` deliberately mean different things:

- `next_review` means judgement is due again. Balanced context includes the
  note with a visible `review-due` state; strict context excludes it.
- `valid_until` is an operational expiry. Context excludes the note after that
  date under every policy.

Every context build records its `as_of` date, freshness policy, selected-note
hashes, relevance reasons, lineage summaries, and exclusions. A written context
therefore remains an inspectable historical artifact even after its inputs
change.

## Progressive Disclosure

Agents should discover before they load:

1. Use `noesis search` or `noesis_search_notes` for ranked summaries and
   lifecycle metadata.
2. Use `context explain` to inspect relevance, freshness, and budget decisions.
3. Load a full note only with `noesis_get_note` when its body is needed.
4. Trace the selected knowledge before changing source-backed claims.

The checked-in retrieval and dogfood evaluations cover the shared contract.
Future domain-specific evaluations should be added before a domain gains new
properties or automation. A custom Obsidian plugin or hosted database remains
out of scope until the file-backed workflow demonstrates a concrete UI or
coordination need that core Obsidian views and these adapters cannot meet.
