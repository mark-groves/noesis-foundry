from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable

import yaml


FOLDERS = [
    "raw",
    "sources",
    "evidence",
    "claims",
    "syntheses",
    "review",
    "knowledge",
    "context",
    "stale",
    "archive/history",
    "_bases",
    "_canvas",
    "_dashboards",
    "_templates",
]

NOTE_FOLDERS = {
    "sources",
    "evidence",
    "claims",
    "syntheses",
    "review",
    "knowledge",
    "context",
    "stale",
    "archive",
    "archive/history",
    "_dashboards",
}

REQUIRED_PROPERTIES = {
    "title",
    "noesis_id",
    "type",
    "lifecycle_stage",
    "status",
    "review_state",
    "confidence",
    "created",
    "updated",
    "tags",
}

TYPES = {
    "source",
    "evidence",
    "claim",
    "synthesis",
    "review",
    "reviewed-knowledge",
    "operational-context",
    "stale-memory",
    "archived-history",
    "dashboard",
}

LIFECYCLE_STAGES = {
    "source",
    "evidence",
    "claim",
    "synthesis",
    "review",
    "knowledge",
    "context",
    "stale",
    "archive",
}

STATUSES = {
    "captured",
    "extracted",
    "draft",
    "needs-review",
    "reviewed",
    "active",
    "complete",
    "stale",
    "superseded",
    "archived",
}

REVIEW_STATES = {
    "none",
    "ready-for-review",
    "in-review",
    "changes-requested",
    "approved",
    "reviewed",
}

CONFIDENCE = {"unknown", "low", "medium", "high"}

REVIEW_DONE = {"none", "approved", "reviewed"}
CURRENT_KNOWLEDGE_STATUSES = {"active", "reviewed"}
EXCLUDED_STATUSES = {"stale", "superseded", "archived"}

RELATIONSHIP_FIELDS = {
    "sources",
    "evidence",
    "claims",
    "syntheses",
    "reviewed_knowledge",
    "reviewed_by",
    "reviewed_notes",
    "supersedes",
    "superseded_by",
    "related_notes",
    "excluded_memory",
}

WIKILINK_RE = re.compile(r"!\[\[([^\]]+)\]\]|\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


@dataclass(frozen=True)
class Issue:
    path: Path
    message: str

    def format(self, vault: Path) -> str:
        try:
            display = self.path.relative_to(vault)
        except ValueError:
            display = self.path
        return f"{display}: {self.message}"


@dataclass
class Note:
    path: Path
    rel_path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def noesis_id(self) -> str:
        return str(self.metadata.get("noesis_id", ""))

    @property
    def title(self) -> str:
        return str(self.metadata.get("title", self.path.stem))

    @property
    def type(self) -> str:
        return str(self.metadata.get("type", ""))

    @property
    def lifecycle_stage(self) -> str:
        return str(self.metadata.get("lifecycle_stage", ""))

    @property
    def status(self) -> str:
        return str(self.metadata.get("status", ""))

    @property
    def review_state(self) -> str:
        return str(self.metadata.get("review_state", ""))


@dataclass(frozen=True)
class CreatedNote:
    note_id: str
    path: Path


@dataclass
class Vault:
    root: Path
    notes: list[Note] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    by_id: dict[str, Note] = field(default_factory=dict)
    by_note_link: dict[str, Note] = field(default_factory=dict)
    by_link: dict[str, Path] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str) -> "Vault":
        root_path = Path(root).expanduser().resolve()
        vault = cls(root=root_path)
        if not root_path.exists():
            vault.issues.append(Issue(root_path, "vault path does not exist"))
            return vault
        if not root_path.is_dir():
            vault.issues.append(Issue(root_path, "vault path is not a directory"))
            return vault

        for path in sorted(root_path.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root_path)
                vault.by_link[path.name] = path
                vault.by_link[path.stem] = path
                vault.by_link[rel.as_posix()] = path
                vault.by_link[rel.with_suffix("").as_posix()] = path

        for path in sorted(root_path.rglob("*.md")):
            rel = path.relative_to(root_path)
            if is_template(rel):
                continue
            if not is_noesis_note(rel):
                continue
            note = read_note(root_path, path)
            if isinstance(note, Issue):
                vault.issues.append(note)
                continue
            vault.notes.append(note)
            vault.register_note_aliases(note)
            if note.noesis_id:
                if note.noesis_id in vault.by_id:
                    vault.issues.append(Issue(path, f"duplicate noesis_id {note.noesis_id!r}"))
                vault.by_id[note.noesis_id] = note
                vault.by_link[note.noesis_id] = path

        return vault

    def validate(self) -> list[Issue]:
        issues = list(self.issues)
        issues.extend(validate_folders(self.root))
        issues.extend(validate_notes(self))
        issues.extend(validate_wikilinks(self))
        issues.extend(validate_bases(self.root))
        issues.extend(validate_canvases(self.root))
        return sorted(issues, key=lambda issue: issue.path.as_posix())

    def review_queue(self) -> list[Note]:
        return sorted(
            (
                note
                for note in self.notes
                if note.review_state not in REVIEW_DONE
                and note.type != "dashboard"
            ),
            key=lambda note: (
                str(note.metadata.get("next_review", "")),
                note.lifecycle_stage,
                note.title.lower(),
            ),
        )

    def find_note(self, ref: str) -> Note | None:
        key = normalize_wikilink_target(ref)
        note = self.by_note_link.get(key) or self.by_id.get(key)
        if note is not None:
            return note
        path = self.by_link.get(key)
        if path:
            return next((note for note in self.notes if note.path == path), None)
        return None

    def register_note_aliases(self, note: Note) -> None:
        rel = note.rel_path
        aliases = [
            note.path.name,
            note.path.stem,
            rel.as_posix(),
            rel.with_suffix("").as_posix(),
            note.noesis_id,
        ]
        aliases.extend(str(alias) for alias in as_list(note.metadata.get("aliases")))
        for alias in aliases:
            if alias:
                self.by_note_link[alias] = note
                self.by_link[alias] = note.path

    def lineage(self, ref: str) -> list[Note]:
        start = self.find_note(ref)
        if start is None:
            return []

        adjacency: dict[str, set[str]] = {note.noesis_id: set() for note in self.notes}
        for note in self.notes:
            for target in iter_metadata_wikilinks(note.metadata):
                target_note = self.find_note(target)
                if target_note is None or not target_note.noesis_id:
                    continue
                adjacency.setdefault(note.noesis_id, set()).add(target_note.noesis_id)
                adjacency.setdefault(target_note.noesis_id, set()).add(note.noesis_id)

        seen: set[str] = set()
        stack = [start.noesis_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(sorted(adjacency.get(current, set()) - seen))

        stage_order = {
            "source": 0,
            "evidence": 1,
            "claim": 2,
            "synthesis": 3,
            "review": 4,
            "knowledge": 5,
            "context": 6,
            "stale": 7,
            "archive": 8,
        }
        return sorted(
            (note for note in self.notes if note.noesis_id in seen),
            key=lambda note: (stage_order.get(note.lifecycle_stage, 99), note.rel_path.as_posix()),
        )

    def current_reviewed_knowledge(self) -> list[Note]:
        return sorted(
            (
                note
                for note in self.notes
                if note.type == "reviewed-knowledge"
                and note.lifecycle_stage == "knowledge"
                and note.review_state in {"reviewed", "approved"}
                and note.status in CURRENT_KNOWLEDGE_STATUSES
                and not is_excluded(note)
            ),
            key=lambda note: note.title.lower(),
        )


def is_template(rel_path: Path) -> bool:
    return rel_path.parts and rel_path.parts[0] == "_templates"


def is_noesis_note(rel_path: Path) -> bool:
    if not rel_path.parts:
        return False
    if rel_path.parts[0] in NOTE_FOLDERS:
        return True
    return False


def read_note(root: Path, path: Path) -> Note | Issue:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return Issue(path, "missing YAML frontmatter")
    raw_frontmatter = match.group(1)
    try:
        metadata = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError as exc:
        return Issue(path, f"invalid YAML frontmatter: {exc}")
    if not isinstance(metadata, dict):
        return Issue(path, "frontmatter must be a YAML mapping")
    for key, value in metadata.items():
        if isinstance(value, dict):
            return Issue(path, f"frontmatter property {key!r} must be flat, not a mapping")
    return Note(
        path=path,
        rel_path=path.relative_to(root),
        metadata=metadata,
        body=text[match.end() :],
    )


def validate_folders(root: Path) -> list[Issue]:
    return [
        Issue(root / folder, "required vault folder is missing")
        for folder in FOLDERS
        if not (root / folder).is_dir()
    ]


def validate_notes(vault: Vault) -> list[Issue]:
    issues: list[Issue] = []
    for note in vault.notes:
        metadata = note.metadata
        missing = sorted(REQUIRED_PROPERTIES - metadata.keys())
        if missing:
            issues.append(Issue(note.path, f"missing required properties: {', '.join(missing)}"))

        for key in sorted(REQUIRED_PROPERTIES - {"tags"}):
            if key in metadata and is_blank(metadata[key]):
                issues.append(Issue(note.path, f"{key} must not be blank"))

        issues.extend(validate_enum(note, "type", TYPES))
        issues.extend(validate_enum(note, "lifecycle_stage", LIFECYCLE_STAGES))
        issues.extend(validate_enum(note, "status", STATUSES))
        issues.extend(validate_enum(note, "review_state", REVIEW_STATES))
        issues.extend(validate_enum(note, "confidence", CONFIDENCE))

        if "tags" in metadata and not isinstance(metadata["tags"], list):
            issues.append(Issue(note.path, "tags must be a YAML list"))

        for date_key in ("created", "updated", "source_date", "captured", "reviewed_at", "next_review"):
            if date_key in metadata and not is_date_like(metadata[date_key]):
                issues.append(Issue(note.path, f"{date_key} must be a date or date-like string"))

        issues.extend(validate_type_stage(note))
        issues.extend(validate_relationship_syntax(note))
        issues.extend(validate_context_exclusions(vault, note))

    return issues


def validate_enum(note: Note, key: str, allowed: set[str]) -> list[Issue]:
    value = note.metadata.get(key)
    if value not in allowed:
        return [Issue(note.path, f"{key} must be one of {', '.join(sorted(allowed))}")]
    return []


def validate_type_stage(note: Note) -> list[Issue]:
    expected = {
        "source": "source",
        "evidence": "evidence",
        "claim": "claim",
        "synthesis": "synthesis",
        "review": "review",
        "reviewed-knowledge": "knowledge",
        "operational-context": "context",
        "stale-memory": "stale",
        "archived-history": "archive",
    }
    if note.type in expected and note.lifecycle_stage != expected[note.type]:
        return [Issue(note.path, f"type {note.type!r} must use lifecycle_stage {expected[note.type]!r}")]
    return []


def validate_relationship_syntax(note: Note) -> list[Issue]:
    issues: list[Issue] = []
    for key in sorted(RELATIONSHIP_FIELDS & note.metadata.keys()):
        for item in as_list(note.metadata.get(key)):
            if not isinstance(item, str):
                issues.append(Issue(note.path, f"{key} relationship entries must be wikilink strings"))
            elif not extract_wikilinks(item):
                issues.append(Issue(note.path, f"{key} relationship entry {item!r} must be a wikilink"))
    return issues


def validate_context_exclusions(vault: Vault, note: Note) -> list[Issue]:
    issues: list[Issue] = []
    if note.type != "operational-context":
        return issues

    for ref in as_list(note.metadata.get("reviewed_knowledge")):
        target = vault.find_note(str(ref))
        if target is None:
            continue
        if target.type != "reviewed-knowledge" or target.review_state not in {"reviewed", "approved"}:
            issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is not reviewed knowledge"))
        elif target.status not in CURRENT_KNOWLEDGE_STATUSES:
            issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is not current reviewed knowledge"))
        elif is_excluded(target):
            issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is stale, superseded, or archived"))

    for ref in as_list(note.metadata.get("excluded_memory")):
        target = vault.find_note(str(ref))
        if target is None:
            continue
        elif not is_excluded(target):
            issues.append(Issue(note.path, f"excluded_memory reference {ref!r} is not stale, superseded, or archived"))

    return issues


def validate_wikilinks(vault: Vault) -> list[Issue]:
    issues: list[Issue] = []
    for note in vault.notes:
        for target in sorted(extract_wikilinks(note.body)):
            if vault.by_link.get(normalize_wikilink_target(target)) is None:
                issues.append(Issue(note.path, f"unresolved wikilink [[{target}]]"))
        for key, target in sorted(iter_metadata_relationship_targets(note.metadata)):
            if vault.find_note(target) is None:
                issues.append(Issue(note.path, f"{key} relationship wikilink [[{target}]] does not resolve to a Noesis note"))
    return issues


def validate_bases(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted((root / "_bases").glob("*.base")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            issues.append(Issue(path, f"invalid Base YAML: {exc}"))
            continue
        if not isinstance(data, dict):
            issues.append(Issue(path, "Base file must contain a YAML mapping"))
            continue
        if "views" not in data:
            issues.append(Issue(path, "Base file is missing views"))
    return issues


def validate_canvases(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted((root / "_canvas").glob("*.canvas")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(Issue(path, f"invalid Canvas JSON: {exc}"))
            continue
        if not isinstance(data, dict):
            issues.append(Issue(path, "Canvas file must contain a JSON object"))
            continue
        node_ids = set()
        for node in data.get("nodes", []):
            if not isinstance(node, dict):
                issues.append(Issue(path, "Canvas nodes must be objects"))
                continue
            if "id" in node:
                node_ids.add(node["id"])
            if node.get("type") == "file" and node.get("file"):
                target = root / str(node["file"])
                if not target.exists():
                    issues.append(Issue(path, f"Canvas file node target is missing: {node['file']}"))
        for edge in data.get("edges", []):
            if not isinstance(edge, dict):
                issues.append(Issue(path, "Canvas edges must be objects"))
                continue
            if edge.get("fromNode") not in node_ids:
                issues.append(Issue(path, f"Canvas edge has missing fromNode: {edge.get('fromNode')}"))
            if edge.get("toNode") not in node_ids:
                issues.append(Issue(path, f"Canvas edge has missing toNode: {edge.get('toNode')}"))
    return issues


def init_vault(path: Path | str, force: bool = False) -> list[Path]:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for folder in FOLDERS:
        target = root / folder
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)

    today = date.today().isoformat()
    files = default_vault_files(today)
    for rel, content in files.items():
        target = root / rel
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(target)

    return created


def ingest_source(
    vault_path: Path | str,
    source_file: Path | str,
    title: str,
    *,
    slug: str | None = None,
    source_type: str = "file",
    original_url: str = "unknown",
    author: str = "unknown",
    source_date: str = "unknown",
    today: str | None = None,
) -> CreatedNote:
    root = ensure_valid_vault(vault_path)
    source_path = Path(source_file).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"source file does not exist: {source_file}")
    if is_blank(title):
        raise ValueError("title must not be blank")
    if not is_date_like(source_date):
        raise ValueError("source_date must be YYYY-MM-DD or unknown")

    created_at = today or date.today().isoformat()
    note_slug = slugify(slug or title)
    raw_name = unique_filename(root / "raw", source_path.name)
    raw_target = root / "raw" / raw_name
    shutil.copy2(source_path, raw_target)

    note_id = unique_noesis_id(root, f"source-{note_slug}")
    note_path = unique_note_path(root / "sources", f"{note_id}.md")
    metadata = {
        "title": title,
        "noesis_id": note_id,
        "type": "source",
        "lifecycle_stage": "source",
        "status": "captured",
        "review_state": "none",
        "confidence": "unknown",
        "created": created_at,
        "updated": created_at,
        "source_type": source_type,
        "raw_path": f"../raw/{raw_name}",
        "original_url": original_url,
        "author": author,
        "source_date": source_date,
        "captured": created_at,
        "tags": ["noesis", "source"],
        "aliases": [],
    }
    body = f"""# {title}

Raw source: [{raw_name}](../raw/{raw_name})

## Summary

## Key Claims

## Evidence Candidates

## Open Questions
"""
    write_note(note_path, metadata, body)
    ensure_valid_vault(root)
    return CreatedNote(note_id=note_id, path=note_path)


def extract_evidence(
    vault_path: Path | str,
    source_ref: str,
    *,
    title: str | None = None,
    evidence: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    source = vault.find_note(source_ref)
    if source is None:
        raise ValueError(f"source note not found: {source_ref}")
    if source.type != "source":
        raise ValueError(f"source reference is not a source note: {source_ref}")

    created_at = today or date.today().isoformat()
    note_title = title or f"Evidence from {source.title}"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"evidence-{note_slug}")
    note_path = unique_note_path(root / "evidence", f"{note_id}.md")
    metadata = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "evidence",
        "lifecycle_stage": "evidence",
        "status": "extracted",
        "review_state": "ready-for-review",
        "confidence": "medium",
        "created": created_at,
        "updated": created_at,
        "sources": [wikilink(source.noesis_id)],
        "tags": ["noesis", "evidence"],
        "aliases": [],
    }
    evidence_text = evidence or "Review this draft against the source and replace this placeholder with atomic evidence."
    body = f"""# {note_title}

## Evidence

{evidence_text}

## Source Basis

- {wikilink(source.noesis_id)}

## Extraction Notes

Generated as a reviewable evidence draft.

## Candidate Claims
"""
    write_note(note_path, metadata, body)
    ensure_valid_vault(root)
    return CreatedNote(note_id=note_id, path=note_path)


def propose_claim(
    vault_path: Path | str,
    evidence_refs: list[str],
    *,
    title: str | None = None,
    claim: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if not evidence_refs:
        raise ValueError("at least one evidence reference is required")
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    evidence_notes: list[Note] = []
    for ref in evidence_refs:
        note = vault.find_note(ref)
        if note is None:
            raise ValueError(f"evidence note not found: {ref}")
        if note.type != "evidence":
            raise ValueError(f"evidence reference is not an evidence note: {ref}")
        evidence_notes.append(note)

    created_at = today or date.today().isoformat()
    note_title = title or f"Claim from {evidence_notes[0].title}"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"claim-{note_slug}")
    note_path = unique_note_path(root / "claims", f"{note_id}.md")
    source_links = sorted(collect_source_links(vault, evidence_notes))
    evidence_links = [wikilink(note.noesis_id) for note in evidence_notes]
    metadata = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "claim",
        "lifecycle_stage": "claim",
        "status": "draft",
        "review_state": "ready-for-review",
        "confidence": "medium",
        "created": created_at,
        "updated": created_at,
        "sources": source_links,
        "evidence": evidence_links,
        "tags": ["noesis", "claim"],
        "aliases": [],
    }
    claim_text = claim or "Review this draft and replace this placeholder with a source-backed claim."
    body = f"""# {note_title}

## Claim

{claim_text}

## Supporting Evidence

{format_link_list(evidence_links)}

## Limits

## Review Notes
"""
    write_note(note_path, metadata, body)
    ensure_valid_vault(root)
    return CreatedNote(note_id=note_id, path=note_path)


def ensure_valid_vault(vault_path: Path | str) -> Path:
    root = Path(vault_path).expanduser().resolve()
    vault = Vault.load(root)
    issues = vault.validate()
    if issues:
        formatted = "; ".join(issue.format(vault.root) for issue in issues[:3])
        remaining = len(issues) - 3
        if remaining > 0:
            formatted = f"{formatted}; and {remaining} more issue(s)"
        raise ValueError(f"vault validation failed before write: {formatted}")
    return root


def default_vault_files(today: str) -> dict[Path, str]:
    return {
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

## Lifecycle Dashboard

![[lifecycle-dashboard.base]]

## Visual Map

Open [[noesis-lifecycle.canvas]].
""",
        Path("review/review-queue.md"): f"""---
title: Review Queue
noesis_id: review-queue
type: review
lifecycle_stage: review
status: active
review_state: none
confidence: unknown
created: {today}
updated: {today}
reviewer: unassigned
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

## Recently Approved
""",
        Path("_bases/review-queue.base"): """filters:
  and:
    - file.inFolder("evidence") || file.inFolder("claims") || file.inFolder("syntheses") || file.inFolder("review") || file.inFolder("knowledge") || file.inFolder("context") || file.inFolder("stale")
    - review_state != "none"
    - review_state != "reviewed"
    - review_state != "approved"
views:
  - type: table
    name: Review queue
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
                    }
                ],
                "edges": [],
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

## Traceability
""",
    }
    return {Path(f"_templates/{name}.md"): content for name, content in templates.items()}


def build_context(vault: Vault, scope: str | None = None, purpose: str | None = None) -> str:
    knowledge = filter_knowledge_by_scope(vault.current_reviewed_knowledge(), scope)
    title = "Noesis Operational Context"
    lines = [f"# {title}", ""]
    if scope:
        lines.extend([f"Scope: {scope}", ""])
    if purpose:
        lines.extend([f"Purpose: {purpose}", ""])
    lines.extend(
        [
            "This context package is built from reviewed knowledge only.",
            "Stale, superseded, and archived memory is excluded.",
            "",
        ]
    )

    if not knowledge:
        lines.extend(["## Reviewed Knowledge", "", "No current reviewed knowledge found.", ""])
        return "\n".join(lines)

    lines.extend(["## Reviewed Knowledge", ""])
    for note in knowledge:
        lines.extend(
            [
                f"### {note.title}",
                "",
                f"- noesis_id: {note.noesis_id}",
                f"- path: {note.rel_path.as_posix()}",
                f"- confidence: {note.metadata.get('confidence', 'unknown')}",
                f"- reviewed_at: {note.metadata.get('reviewed_at', 'unknown')}",
                "",
                note.body.strip(),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def filter_knowledge_by_scope(knowledge: list[Note], scope: str | None) -> list[Note]:
    if scope is None or not scope.strip():
        return knowledge
    normalized_scope = scope.strip().lower()
    return [note for note in knowledge if normalized_scope in searchable_note_text(note)]


def searchable_note_text(note: Note) -> str:
    metadata_values = [
        note.noesis_id,
        note.title,
        note.rel_path.as_posix(),
    ]
    for key in ("tags", "aliases"):
        for value in as_list(note.metadata.get(key)):
            metadata_values.append(str(value))
    metadata_values.append(note.body)
    return "\n".join(metadata_values).lower()


def is_excluded(note: Note) -> bool:
    return note.lifecycle_stage in {"stale", "archive"} or note.status in EXCLUDED_STATUSES


def write_note(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body.rstrip()}\n", encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def wikilink(target: str) -> str:
    return f"[[{target}]]"


def format_link_list(links: list[str]) -> str:
    if not links:
        return ""
    return "\n".join(f"- {link}" for link in links)


def collect_source_links(vault: Vault, notes: list[Note]) -> set[str]:
    links: set[str] = set()
    for note in notes:
        for target in iter_metadata_wikilinks(note.metadata):
            target_note = vault.find_note(target)
            if target_note is not None and target_note.type == "source":
                links.add(wikilink(target_note.noesis_id))
    return links


def unique_filename(folder: Path, filename: str) -> str:
    candidate = Path(filename).name
    if not (folder / candidate).exists():
        return candidate
    stem = Path(candidate).stem
    suffix = Path(candidate).suffix
    counter = 2
    while True:
        next_candidate = f"{stem}-{counter}{suffix}"
        if not (folder / next_candidate).exists():
            return next_candidate
        counter += 1


def unique_note_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        next_candidate = folder / f"{stem}-{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def unique_noesis_id(root: Path, base_id: str) -> str:
    existing = Vault.load(root).by_id
    if base_id not in existing:
        return base_id
    counter = 2
    while True:
        candidate = f"{base_id}-{counter}"
        if candidate not in existing:
            return candidate
        counter += 1


def is_date_like(value: Any) -> bool:
    if isinstance(value, date):
        return True
    if isinstance(value, str):
        if value in {"unknown", "{{date}}"}:
            return True
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    return False


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_wikilinks(text: str) -> set[str]:
    return {
        target
        for match in WIKILINK_RE.finditer(text)
        if (target := normalize_wikilink_target(match.group(1) or match.group(2)))
    }


def iter_metadata_wikilinks(metadata: dict[str, Any]) -> Iterable[str]:
    for _, target in iter_metadata_relationship_targets(metadata):
        yield target


def iter_metadata_relationship_targets(metadata: dict[str, Any]) -> Iterable[tuple[str, str]]:
    for key, value in metadata.items():
        if key not in RELATIONSHIP_FIELDS:
            continue
        for item in as_list(value):
            if isinstance(item, str):
                matches = extract_wikilinks(item)
                if matches:
                    for target in matches:
                        yield key, target


def normalize_wikilink_target(target: str) -> str:
    normalized = target.strip()
    if normalized.startswith("[[") and normalized.endswith("]]"):
        normalized = normalized[2:-2]
    if "|" in normalized:
        normalized = normalized.split("|", 1)[0]
    if "#" in normalized:
        normalized = normalized.split("#", 1)[0]
    return normalized.strip()
