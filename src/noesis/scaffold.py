"""Default vault workbench and note-template scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

from .vault import (
    CONTRACT_FILE,
    CONTRACT_KIND,
    CONTRACT_SOURCE_OF_TRUTH,
    CONTRACT_VERSION,
    NOESIS_VERSION,
)


def default_vault_files(today: str) -> dict[Path, str]:
    return {
        CONTRACT_FILE: f"""noesis_contract: {CONTRACT_KIND}
contract_version: "{CONTRACT_VERSION}"
source_of_truth: {CONTRACT_SOURCE_OF_TRUTH}
requires_noesis: ">={NOESIS_VERSION}"
created: {today}
updated: {today}
""",
        Path("_dashboards/noesis-review-dashboard.md"): f"""---
title: Noesis Review Dashboard
noesis_id: dashboard-review
type: dashboard
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: {today}
updated: {today}
tags:
  - noesis
  - dashboard
---

# Noesis Review Dashboard

## Review Queue

![[review-queue.base]]

## CLI Review Workbench

Use these read-only inspection commands when a row needs
closer inspection:

```bash
noesis review summary --vault <vault-path>
noesis review queue --vault <vault-path> --due --due-on {today}
noesis review show <note-id> --vault <vault-path>
```

`review summary`, `review queue`, and `review show` report overdue review
status, audit gaps, requested changes, downstream reviewed-knowledge/context
impact, and complete lineage.

Use this write action after a scheduled review confirms the note still fits
its current lifecycle role:

```bash
noesis review renew <note-id> --vault <vault-path> --reviewer <reviewer-id> --basis "<why this lifecycle role remains valid>" --next-review <YYYY-MM-DD>
```

`review renew` records the scheduled review audit and moves `next_review`
without changing active, stale, or superseded lifecycle status.

Use the Direct audit link checks Base view as a frontmatter shortcut only; the
CLI review summary remains authoritative for audit gaps because review notes
can also link targets through `reviewed_notes`.

## Lifecycle Dashboard

![[lifecycle-dashboard.base]]

## Traceability Workbench

![[traceability-workbench.base]]

Use this Base to inspect lineage links, review audit notes, active context
packages, and excluded memory before changing lifecycle state. It is a view over
frontmatter and wikilinks only; notes remain canonical.

## Visual Map

Open [[noesis-lifecycle.canvas]].
""",
        Path("review/review-queue.md"): f"""---
title: Review Queue
noesis_id: review-queue
type: dashboard
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: {today}
updated: {today}
next_review: {today}
tags:
  - noesis
  - review
  - queue
aliases:
  - Noesis review queue
---

# Review Queue

The canonical sortable queue is [[review-queue.base]].

## Ready For Review

## Overdue Scheduled Reviews

Use `review show <note-id>` before renewing a stale or superseded note. Renewal
records the audit and reschedules `next_review` without making stale memory
active context again.

## Requested Changes

Notes here should be resolved before they support new synthesis, reviewed
knowledge, or operational context.

## Downstream Impact Checks

Inspect dependent reviewed knowledge and context before changing or retiring a
note with support links, `reviewed_knowledge`, `excluded_memory`, or
`superseded_by` metadata.

## Recently Approved
""",
        Path("_bases/review-queue.base"): """filters:
  and:
    - file.inFolder("evidence") || file.inFolder("claims") || file.inFolder("syntheses") || file.inFolder("review") || file.inFolder("knowledge") || file.inFolder("context") || file.inFolder("stale")
views:
  - type: table
    name: Open review queue
    filters:
      and:
        - review_state != "none"
        - review_state != "reviewed"
        - review_state != "approved"
    groupBy:
      property: review_state
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - confidence
      - next_review
      - updated
  - type: table
    name: Due and scheduled reviews
    filters:
      and:
        - next_review != null
        - review_state != "none"
        - type != "review"
    groupBy:
      property: next_review
      direction: ASC
    order:
      - next_review
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - reviewed_by
      - superseded_by
  - type: table
    name: Requested changes
    filters:
      and:
        - review_state == "changes-requested"
    groupBy:
      property: lifecycle_stage
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - reviewed_by
      - updated
  - type: table
    name: Downstream impact cues
    filters:
      and:
        - reviewed_knowledge != null || excluded_memory != null || superseded_by != null
    groupBy:
      property: type
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - reviewed_knowledge
      - excluded_memory
      - superseded_by
      - updated
  - type: table
    name: Direct audit link checks
    filters:
      and:
        - review_state == "approved" || review_state == "reviewed"
        - type == "evidence" || type == "claim" || type == "synthesis" || type == "reviewed-knowledge"
        - reviewed_by == null
    groupBy:
      property: type
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - reviewed_by
      - updated
""",
        Path("_bases/lifecycle-dashboard.base"): """filters:
  and:
    - file.inFolder("sources") || file.inFolder("evidence") || file.inFolder("claims") || file.inFolder("syntheses") || file.inFolder("review") || file.inFolder("knowledge") || file.inFolder("context") || file.inFolder("stale") || file.inFolder("archive") || file.inFolder("archive/history")
    - noesis_id != null
views:
  - type: table
    name: Lifecycle dashboard
    groupBy:
      property: lifecycle_stage
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - confidence
      - updated
  - type: table
    name: Active, stale, and archived state
    groupBy:
      property: status
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - superseded_by
      - next_review
      - updated
  - type: table
    name: Review readiness by stage
    filters:
      and:
        - review_state != "none"
    groupBy:
      property: review_state
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - review_state
      - confidence
      - next_review
""",
        Path("_bases/traceability-workbench.base"): """filters:
  and:
    - file.inFolder("sources") || file.inFolder("evidence") || file.inFolder("claims") || file.inFolder("syntheses") || file.inFolder("review") || file.inFolder("knowledge") || file.inFolder("context") || file.inFolder("stale") || file.inFolder("archive") || file.inFolder("archive/history")
    - noesis_id != null
views:
  - type: table
    name: Lineage support links
    filters:
      and:
        - type != "dashboard"
        - type != "review"
    groupBy:
      property: lifecycle_stage
      direction: ASC
    order:
      - file.name
      - type
      - lifecycle_stage
      - status
      - sources
      - evidence
      - claims
      - syntheses
      - reviewed_knowledge
  - type: table
    name: Review audit records
    filters:
      and:
        - type == "review"
        - reviewed_notes != null
    groupBy:
      property: decision
      direction: ASC
    order:
      - reviewed_at
      - file.name
      - decision
      - reviewer
      - reviewed_notes
      - next_review
  - type: table
    name: Active context packages
    filters:
      and:
        - type == "operational-context"
        - status == "active"
    groupBy:
      property: review_state
      direction: ASC
    order:
      - file.name
      - reviewed_knowledge
      - excluded_memory
      - next_review
      - updated
  - type: table
    name: Context exclusions and superseded memory
    filters:
      and:
        - excluded_memory != null || superseded_by != null || status == "stale" || status == "superseded" || status == "archived" || lifecycle_stage == "archive"
    groupBy:
      property: lifecycle_stage
      direction: ASC
    order:
      - file.name
      - type
      - status
      - review_state
      - excluded_memory
      - superseded_by
      - next_review
      - updated
""",
        Path("_canvas/noesis-lifecycle.canvas"): json.dumps(
            {
                "nodes": [
                    {
                        "id": "dashboard",
                        "type": "file",
                        "file": "_dashboards/noesis-review-dashboard.md",
                        "x": 0,
                        "y": 0,
                        "width": 360,
                        "height": 180,
                    },
                    {
                        "id": "review-queue-note",
                        "type": "file",
                        "file": "review/review-queue.md",
                        "x": 440,
                        "y": 0,
                        "width": 320,
                        "height": 180,
                    },
                    {
                        "id": "review-base",
                        "type": "file",
                        "file": "_bases/review-queue.base",
                        "x": 0,
                        "y": 260,
                        "width": 320,
                        "height": 160,
                    },
                    {
                        "id": "lifecycle-base",
                        "type": "file",
                        "file": "_bases/lifecycle-dashboard.base",
                        "x": 380,
                        "y": 260,
                        "width": 320,
                        "height": 160,
                    },
                    {
                        "id": "traceability-base",
                        "type": "file",
                        "file": "_bases/traceability-workbench.base",
                        "x": 760,
                        "y": 260,
                        "width": 320,
                        "height": 160,
                    },
                    {
                        "id": "review-template",
                        "type": "file",
                        "file": "_templates/review.md",
                        "x": 0,
                        "y": 500,
                        "width": 320,
                        "height": 160,
                    },
                    {
                        "id": "context-template",
                        "type": "file",
                        "file": "_templates/operational-context.md",
                        "x": 380,
                        "y": 500,
                        "width": 320,
                        "height": 160,
                    }
                ],
                "edges": [
                    {
                        "id": "dashboard-review-note",
                        "fromNode": "dashboard",
                        "fromSide": "right",
                        "toNode": "review-queue-note",
                        "toSide": "left",
                    },
                    {
                        "id": "dashboard-review-base",
                        "fromNode": "dashboard",
                        "fromSide": "bottom",
                        "toNode": "review-base",
                        "toSide": "top",
                    },
                    {
                        "id": "review-base-lifecycle-base",
                        "fromNode": "review-base",
                        "fromSide": "right",
                        "toNode": "lifecycle-base",
                        "toSide": "left",
                    },
                    {
                        "id": "lifecycle-base-traceability-base",
                        "fromNode": "lifecycle-base",
                        "fromSide": "right",
                        "toNode": "traceability-base",
                        "toSide": "left",
                    },
                    {
                        "id": "traceability-base-review-template",
                        "fromNode": "traceability-base",
                        "fromSide": "bottom",
                        "toNode": "review-template",
                        "toSide": "top",
                    },
                    {
                        "id": "traceability-base-context-template",
                        "fromNode": "traceability-base",
                        "fromSide": "bottom",
                        "toNode": "context-template",
                        "toSide": "top",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        Path(".obsidian/core-plugins.json"): json.dumps(
            {
                "file-explorer": True,
                "global-search": True,
                "switcher": True,
                "graph": True,
                "backlink": True,
                "canvas": True,
                "outgoing-link": True,
                "properties": True,
                "templates": True,
                "command-palette": True,
                "bookmarks": True,
                "file-recovery": True,
                "bases": True,
            },
            indent=2,
        )
        + "\n",
        Path(".obsidian/app.json"): "{}\n",
        Path(".obsidian/appearance.json"): "{}\n",
        Path(".obsidian/graph.json"): "{}\n",
        Path(".obsidian/workspace.json"): "{}\n",
        **template_files(today),
    }


def template_files(today: str) -> dict[Path, str]:
    templates: dict[str, str] = {
        "source": """---
title: "{{title}}"
noesis_id: "source-<slug>"
type: source
lifecycle_stage: source
status: captured
review_state: none
confidence: unknown
created: "{{date}}"
updated: "{{date}}"
source_type: unknown
raw_path: "../raw/<raw_filename>"
original_url: unknown
author: unknown
source_date: unknown
captured: "{{date}}"
content_hash: unknown
content_hash_algorithm: sha256
source_size_bytes: unknown
original_path: unknown
tags:
  - noesis
  - source
aliases: []
---

# {{title}}

Raw source: [<raw_filename>](../raw/<raw_filename>)

## Summary

## Key Claims

## Evidence Candidates

## Open Questions
""",
        "evidence": """---
title: "{{title}}"
noesis_id: "evidence-<slug>"
type: evidence
lifecycle_stage: evidence
status: extracted
review_state: none
confidence: medium
created: "{{date}}"
updated: "{{date}}"
sources:
  - "[[<source-note>]]"
tags:
  - noesis
  - evidence
aliases: []
---

# {{title}}

## Evidence

## Source Basis

## Extraction Notes

## Candidate Claims
""",
        "claim": """---
title: "{{title}}"
noesis_id: "claim-<slug>"
type: claim
lifecycle_stage: claim
status: draft
review_state: ready-for-review
confidence: medium
created: "{{date}}"
updated: "{{date}}"
sources:
  - "[[<source-note>]]"
evidence:
  - "[[<evidence-note>]]"
tags:
  - noesis
  - claim
aliases: []
---

# {{title}}

## Claim

## Supporting Evidence

## Limits

## Review Notes

## Lifecycle Impact

## Context Safety
""",
        "synthesis": """---
title: "{{title}}"
noesis_id: "synthesis-<slug>"
type: synthesis
lifecycle_stage: synthesis
status: draft
review_state: ready-for-review
confidence: medium
created: "{{date}}"
updated: "{{date}}"
sources:
  - "[[<source-note>]]"
evidence:
  - "[[<evidence-note>]]"
claims:
  - "[[<claim-note>]]"
tags:
  - noesis
  - synthesis
aliases: []
---

# {{title}}

## Synthesis

## Supporting Claims

## Tensions Or Gaps

## Implications

## Context Safety
""",
        "review": """---
title: "{{title}}"
noesis_id: "review-<slug>"
type: review
lifecycle_stage: review
status: complete
review_state: approved
confidence: medium
created: "{{date}}"
updated: "{{date}}"
reviewer: unknown
reviewed_at: "{{date}}"
reviewed_notes:
  - "[[<note-under-review>]]"
decision: approved
tags:
  - noesis
  - review
aliases: []
---

# {{title}}

## Decision

## Basis

## Changes Requested

## Lineage Checked

## Context Safety

## Next Review
""",
        "operational-context": """---
title: "{{title}}"
noesis_id: "context-<slug>"
type: operational-context
lifecycle_stage: context
status: active
review_state: reviewed
confidence: medium
created: "{{date}}"
updated: "{{date}}"
syntheses:
  - "[[<synthesis-note>]]"
reviewed_knowledge:
  - "[[<reviewed-knowledge-note>]]"
excluded_memory: []
freshness_excluded: []
as_of: "{{date}}"
freshness_policy: balanced
input_hashes:
  - "<reviewed-knowledge-noesis-id>=sha256:<content-digest>"
next_review: "{{date}}"
tags:
  - noesis
  - context
aliases: []
---

# {{title}}

## Use This Context For

## Current Guidance

## Do Not Use

## Context Exclusions

## Traceability
""",
    }
    return {Path(f"_templates/{name}.md"): content for name, content in templates.items()}
