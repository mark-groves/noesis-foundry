from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any, Iterable, Sequence

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

CONTRACT_FILE = Path("noesis.vault.yaml")
CONTRACT_VERSION = "1"
CONTRACT_KIND = "vault"
CONTRACT_SOURCE_OF_TRUTH = "markdown-flat-yaml"
NOESIS_VERSION = "0.1.0"
SOURCE_BUNDLE_SCHEMA_VERSION = "1"
SOURCE_BUNDLE_SCHEMA_KIND = "noesis-source-bundle"
SOURCE_BUNDLE_REQUIRED_ARTIFACT_FIELDS = {"path"}
SOURCE_BUNDLE_TOP_LEVEL_FIELDS = {
    "schema_version",
    "bundle_id",
    "title",
    "source_type",
    "original_url",
    "author",
    "source_date",
    "artifacts",
}
SOURCE_BUNDLE_ARTIFACT_FIELDS = {
    "path",
    "id",
    "title",
    "slug",
    "source_type",
    "original_url",
    "author",
    "source_date",
    "evidence_title",
    "evidence",
    "evidence_slug",
}
CONTRACT_REQUIRED_PROPERTIES = {
    "noesis_contract",
    "contract_version",
    "source_of_truth",
    "requires_noesis",
    "created",
    "updated",
}

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


@dataclass(frozen=True)
class ContextSelection:
    note: Note
    status: str
    reason: str
    score: int
    content_chars: int


@dataclass(frozen=True)
class ContextProfile:
    name: str
    description: str
    default_limit: int | None
    default_max_chars: int | None


@dataclass(frozen=True)
class ContextLineageSummary:
    reviewed_knowledge: Note
    sources: list[Note]
    evidence: list[Note]
    claims: list[Note]
    syntheses: list[Note]
    reviews: list[Note]


@dataclass(frozen=True)
class ContextHandoffGuidance:
    task_purpose: str
    assumptions: list[str]
    validation_commands: list[str]
    next_steps: list[str]


CONTEXT_PROFILES = {
    "project-continuation": ContextProfile(
        name="project-continuation",
        description="Prefer a broad, current briefing for continuing implementation work.",
        default_limit=8,
        default_max_chars=16000,
    ),
    "codex-handoff": ContextProfile(
        name="codex-handoff",
        description="Render a Codex-ready handoff pack for launching a separate agent thread.",
        default_limit=6,
        default_max_chars=14000,
    ),
    "research": ContextProfile(
        name="research",
        description="Prefer a larger evidence-oriented briefing for discovery and synthesis work.",
        default_limit=10,
        default_max_chars=24000,
    ),
    "review": ContextProfile(
        name="review",
        description="Prefer a tighter briefing for evaluating changes and lifecycle state.",
        default_limit=6,
        default_max_chars=12000,
    ),
}
CONTEXT_PROFILE_NAMES = set(CONTEXT_PROFILES)


@dataclass(frozen=True)
class ContextPackage:
    profile: str | None
    profile_description: str | None
    scope: str | None
    purpose: str | None
    limit: int | None
    max_chars: int | None
    requested_limit: int | None
    requested_max_chars: int | None
    applied_profile_defaults: tuple[str, ...]
    available_count: int
    included: list[ContextSelection]
    excluded: list[ContextSelection]
    scoped_out: list[ContextSelection]
    budgeted_out: list[ContextSelection]
    lifecycle_excluded: list[ContextSelection]
    lineage_summaries: list[ContextLineageSummary]
    handoff: ContextHandoffGuidance
    content: str

    @property
    def reviewed_knowledge(self) -> list[Note]:
        return [selection.note for selection in self.included]


@dataclass(frozen=True)
class VaultDoctor:
    root: Path
    contract_path: Path
    contract: dict[str, Any]
    contract_issues: list[Issue]
    validation_issues: list[Issue]
    note_count: int

    @property
    def compatible(self) -> bool:
        return not self.contract_issues

    @property
    def complete(self) -> bool:
        return not self.validation_issues

    @property
    def ready_for_cli_mcp(self) -> bool:
        return self.compatible and self.complete


@dataclass(frozen=True)
class SourceCaptureResult:
    status: str
    source_file: Path
    title: str
    content_hash: str
    note: CreatedNote | None = None
    raw_path: Path | None = None
    evidence_note: CreatedNote | None = None
    existing_note_id: str | None = None
    existing_note_path: Path | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SourceBundleImportResult:
    bundle_id: str
    title: str
    schema_version: str
    bundle_path: Path
    manifest_path: Path
    manifest_hash: str
    results: list[SourceCaptureResult]


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
        issues.extend(validate_contract(self.root))
        issues.extend(validate_folders(self.root))
        issues.extend(validate_notes(self))
        issues.extend(validate_wikilinks(self))
        issues.extend(validate_bases(self.root))
        issues.extend(validate_canvases(self.root))
        return sorted(issues, key=lambda issue: issue.path.as_posix())

    def doctor(self) -> VaultDoctor:
        contract = read_contract(self.root)
        contract_issues = validate_contract(self.root)
        validation_issues = self.validate()
        return VaultDoctor(
            root=self.root,
            contract_path=self.root / CONTRACT_FILE,
            contract=contract,
            contract_issues=contract_issues,
            validation_issues=validation_issues,
            note_count=len(self.notes),
        )

    def review_queue(
        self,
        *,
        review_state: str | None = None,
        note_type: str | None = None,
        lifecycle_stage: str | None = None,
        due: bool = False,
        due_on: str | date | None = None,
    ) -> list[Note]:
        if due:
            review_cutoff_date(due_on)
        notes: list[Note] = []
        for note in self.notes:
            if note.type == "dashboard":
                continue
            if due and note.type == "review":
                continue
            if review_state is None:
                if due:
                    if note.review_state == "none":
                        continue
                elif note.review_state in REVIEW_DONE:
                    continue
            elif note.review_state != review_state:
                continue
            if note_type is not None and note.type != note_type:
                continue
            if lifecycle_stage is not None and note.lifecycle_stage != lifecycle_stage:
                continue
            if due and not note_review_due(note, due_on=due_on):
                continue
            notes.append(note)
        return sort_review_notes(notes)

    def review_summary(self, *, due_on: str | date | None = None) -> dict[str, Any]:
        cutoff = review_cutoff_date(due_on)
        reviewable_notes = [note for note in self.notes if note.type != "dashboard"]
        review_counts: dict[str, int] = {}
        for note in reviewable_notes:
            review_counts[note.review_state] = review_counts.get(note.review_state, 0) + 1
        scheduled_candidates = [
            note
            for note in reviewable_notes
            if note.type != "review" and note.review_state != "none"
        ]
        due_notes = sort_review_notes(
            [note for note in scheduled_candidates if note_review_due(note, due_on=due_on)]
        )
        scheduled_notes = sort_review_notes(
            [note for note in scheduled_candidates if parse_review_date(note.metadata.get("next_review")) is not None]
        )
        overdue_notes = sort_review_notes(
            [
                note
                for note in scheduled_candidates
                if (next_review := parse_review_date(note.metadata.get("next_review"))) is not None
                and next_review < cutoff
            ]
        )
        requested_changes_notes = sort_review_notes(
            [note for note in reviewable_notes if note.review_state == "changes-requested"]
        )
        audit_gap_notes = sort_review_notes(
            [
                note
                for note in reviewable_notes
                if review_requires_audit(note) and not self.review_audits_for(note)
            ]
        )
        return {
            "review_state_counts": dict(sorted(review_counts.items())),
            "pending_count": len(self.review_queue()),
            "due_count": len(due_notes),
            "overdue_count": len(overdue_notes),
            "requested_changes_count": len(requested_changes_notes),
            "audit_gap_count": len(audit_gap_notes),
            "due_notes": due_notes,
            "overdue_notes": overdue_notes,
            "requested_changes_notes": requested_changes_notes,
            "audit_gap_notes": audit_gap_notes,
            "next_review_notes": scheduled_notes[:10],
        }

    def review_audits_for(self, target: Note) -> list[Note]:
        audits: list[Note] = []
        for note in self.notes:
            if note.type != "review":
                continue
            if relationship_contains(self, note.metadata, "reviewed_notes", target.noesis_id):
                audits.append(note)
                continue
            if relationship_contains(self, target.metadata, "reviewed_by", note.noesis_id):
                audits.append(note)
        relationship_order = self.review_audit_relationship_order(target)
        return sorted(
            audits,
            key=lambda note: (
                str(note.metadata.get("reviewed_at", note.metadata.get("updated", ""))),
                relationship_order.get(note.noesis_id, -1),
                note.title.lower(),
                note.rel_path.as_posix(),
            ),
        )

    def review_audit_relationship_order(self, target: Note) -> dict[str, int]:
        order: dict[str, int] = {}
        for index, item in enumerate(as_list(target.metadata.get("reviewed_by"))):
            if not isinstance(item, str):
                continue
            for link_target in extract_wikilinks(item):
                note = self.find_note(link_target)
                if note is None or note.type != "review":
                    continue
                order.setdefault(note.noesis_id, index)
        return order

    def support_notes_for(self, target: Note) -> dict[str, list[Note]]:
        support: dict[str, list[Note]] = {}
        for key in sorted(RELATIONSHIP_FIELDS & target.metadata.keys()):
            notes: list[Note] = []
            seen: set[str] = set()
            for item in as_list(target.metadata.get(key)):
                if not isinstance(item, str):
                    continue
                for link_target in extract_wikilinks(item):
                    note = self.find_note(link_target)
                    if note is None or note.noesis_id in seen:
                        continue
                    notes.append(note)
                    seen.add(note.noesis_id)
            if notes:
                support[key] = sorted(notes, key=lambda note: (note.lifecycle_stage, note.rel_path.as_posix()))
        return support

    def dependent_reviewed_knowledge_for(self, target: Note) -> list[Note]:
        return sorted(
            (
                note
                for note in self.notes
                if note.type == "reviewed-knowledge"
                and note.noesis_id != target.noesis_id
                and note_references_memory(self, note, target.noesis_id)
            ),
            key=lambda note: note.rel_path.as_posix(),
        )

    def dependent_contexts_for(self, target: Note) -> list[Note]:
        return sorted(
            (
                note
                for note in self.notes
                if note.type == "operational-context"
                and (
                    context_references_memory(self, note, target.noesis_id)
                    or relationship_contains(self, note.metadata, "excluded_memory", target.noesis_id)
                )
            ),
            key=lambda note: note.rel_path.as_posix(),
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


def read_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_FILE
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def validate_contract(root: Path) -> list[Issue]:
    path = root / CONTRACT_FILE
    if not root.exists():
        return [
            Issue(
                path,
                f"missing Noesis V{CONTRACT_VERSION} contract metadata because vault path does not exist",
            )
        ]
    if not root.is_dir():
        return [
            Issue(
                root,
                f"missing Noesis V{CONTRACT_VERSION} contract metadata because vault path is not a directory",
            )
        ]
    if not path.exists():
        return [
            Issue(
                path,
                f"missing Noesis V{CONTRACT_VERSION} contract metadata; run noesis vault init <path> to add it",
            )
        ]
    if not path.is_file():
        return [Issue(path, "Noesis contract metadata path is not a file")]

    try:
        metadata = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [Issue(path, f"invalid Noesis contract YAML: {exc}")]
    if not isinstance(metadata, dict):
        return [Issue(path, "Noesis contract metadata must be a YAML mapping")]

    issues: list[Issue] = []
    for key, value in metadata.items():
        if isinstance(value, dict):
            issues.append(Issue(path, f"Noesis contract property {key!r} must be flat, not a mapping"))

    missing = sorted(CONTRACT_REQUIRED_PROPERTIES - metadata.keys())
    if missing:
        issues.append(Issue(path, f"missing Noesis contract properties: {', '.join(missing)}"))

    if metadata.get("noesis_contract") != CONTRACT_KIND:
        issues.append(Issue(path, f"noesis_contract must be {CONTRACT_KIND!r}"))
    if str(metadata.get("contract_version", "")) != CONTRACT_VERSION:
        issues.append(Issue(path, f"contract_version must be supported version {CONTRACT_VERSION!r}"))
    if metadata.get("source_of_truth") != CONTRACT_SOURCE_OF_TRUTH:
        issues.append(Issue(path, f"source_of_truth must be {CONTRACT_SOURCE_OF_TRUTH!r}"))
    if "requires_noesis" in metadata:
        issues.extend(validate_requires_noesis(path, metadata["requires_noesis"]))
    for date_key in ("created", "updated"):
        if date_key in metadata and not is_date_like(metadata[date_key]):
            issues.append(Issue(path, f"{date_key} must be a date or date-like string"))

    return issues


def validate_requires_noesis(path: Path, value: Any) -> list[Issue]:
    if not isinstance(value, str):
        return [Issue(path, "requires_noesis must be a string like '>=0.1.0'")]

    match = re.fullmatch(r">=\s*(\d+)\.(\d+)\.(\d+)", value.strip())
    if match is None:
        return [Issue(path, "requires_noesis must use a supported minimum version like '>=0.1.0'")]

    required = tuple(int(part) for part in match.groups())
    current = parse_version_tuple(NOESIS_VERSION)
    if current < required:
        return [Issue(path, f"requires_noesis {value!r} is newer than this CLI version {NOESIS_VERSION}")]
    return []


def parse_version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError(f"invalid Noesis version: {value}")
    return tuple(int(part) for part in match.groups())


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
    allow_duplicate: bool = False,
) -> CreatedNote:
    result = capture_source(
        vault_path,
        source_file,
        title,
        slug=slug,
        source_type=source_type,
        original_url=original_url,
        author=author,
        source_date=source_date,
        today=today,
        allow_duplicate=allow_duplicate,
    )
    if result.note is None:
        raise ValueError(f"source already captured: {result.existing_note_id}")
    return result.note


def ingest_sources(
    vault_path: Path | str,
    source_files: Sequence[Path | str],
    *,
    source_root: Path | str | None = None,
    title: str | None = None,
    slug: str | None = None,
    source_type: str = "file",
    original_url: str = "unknown",
    author: str = "unknown",
    source_date: str = "unknown",
    today: str | None = None,
    allow_duplicates: bool = False,
    create_evidence: bool = False,
) -> list[SourceCaptureResult]:
    root = ensure_valid_vault(vault_path)
    source_paths = deterministic_source_paths(source_files)
    if not source_paths:
        raise ValueError("no source files found")
    if title is not None and len(source_paths) > 1:
        raise ValueError("--title can only be used with one source file")
    if slug is not None and len(source_paths) > 1:
        raise ValueError("--slug can only be used with one source file")
    if not is_date_like(source_date):
        raise ValueError("source_date must be YYYY-MM-DD or unknown")

    results: list[SourceCaptureResult] = []
    resolved_root = Path(source_root).expanduser().resolve() if source_root is not None else None
    for source_path in source_paths:
        source_title = title or title_from_source_path(source_path, source_root=resolved_root)
        source_slug = slug or slug_from_source_path(source_path, source_root=resolved_root)
        result = capture_source(
            root,
            source_path,
            source_title,
            slug=source_slug,
            source_type=source_type,
            original_url=original_url,
            author=author,
            source_date=source_date,
            today=today,
            allow_duplicate=allow_duplicates,
        )
        if create_evidence and result.note is not None:
            evidence = extract_evidence(root, result.note.note_id, today=today)
            result = SourceCaptureResult(
                status=result.status,
                source_file=result.source_file,
                title=result.title,
                content_hash=result.content_hash,
                note=result.note,
                raw_path=result.raw_path,
                evidence_note=evidence,
                existing_note_id=result.existing_note_id,
                existing_note_path=result.existing_note_path,
                reason=result.reason,
            )
        results.append(result)
    return results


def import_source_bundle(
    vault_path: Path | str,
    bundle_path: Path | str,
    *,
    manifest_name: str = "noesis-bundle.yaml",
    create_evidence: bool = False,
    allow_duplicates: bool = False,
    today: str | None = None,
) -> SourceBundleImportResult:
    root = ensure_valid_vault(vault_path)
    manifest_path = resolve_bundle_manifest(bundle_path, manifest_name)
    manifest = read_source_bundle_manifest(manifest_path)
    bundle_root = manifest_path.parent.resolve()
    schema_version = source_bundle_schema_version(manifest)
    bundle_title = manifest_text(manifest, "title", default=title_from_source_path(bundle_root))
    bundle_id = slugify(manifest_text(manifest, "bundle_id", default=bundle_title))
    bundle_source_type = manifest_text(manifest, "source_type", default="project-artifact-bundle")
    bundle_original_url = manifest_text(manifest, "original_url", default="unknown")
    bundle_author = manifest_text(manifest, "author", default="unknown")
    bundle_source_date = manifest_text(manifest, "source_date", default="unknown")
    if not is_date_like(bundle_source_date):
        raise ValueError("bundle source_date must be YYYY-MM-DD or unknown")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("bundle manifest must contain a non-empty artifacts list")

    manifest_hash = file_content_hash(manifest_path)
    parsed_items: list[tuple[str, int, Path, dict[str, Any]]] = []
    seen_artifact_paths: dict[str, int] = {}
    for manifest_index, entry in enumerate(artifacts, start=1):
        item = normalize_bundle_artifact(entry, manifest_index)
        artifact_rel = Path(manifest_text(item, "path"))
        artifact_path = resolve_bundle_artifact(bundle_root, artifact_rel)
        artifact_key = artifact_rel.as_posix()
        if artifact_key in seen_artifact_paths:
            previous_index = seen_artifact_paths[artifact_key]
            raise ValueError(
                "bundle manifest lists artifact path "
                f"{artifact_key} more than once at indexes {previous_index} and {manifest_index}"
            )
        seen_artifact_paths[artifact_key] = manifest_index
        parsed_items.append((artifact_rel.as_posix(), manifest_index, artifact_path, item))

    prepared_items: list[dict[str, Any]] = []
    seen_item_ids: dict[str, str] = {}
    for bundle_item_index, (artifact_rel, manifest_index, artifact_path, item) in enumerate(
        sorted(parsed_items, key=lambda parsed: (parsed[0], parsed[1])),
        start=1,
    ):
        source_title = manifest_text(
            item,
            "title",
            default=title_from_source_path(artifact_path, source_root=bundle_root),
        )
        source_slug = manifest_text(
            item,
            "slug",
            default=slug_from_source_path(artifact_path, source_root=bundle_root),
        )
        source_type = manifest_text(item, "source_type", default=bundle_source_type)
        original_url = manifest_text(item, "original_url", default=bundle_original_url)
        author = manifest_text(item, "author", default=bundle_author)
        source_date = manifest_text(item, "source_date", default=bundle_source_date)
        if not is_date_like(source_date):
            raise ValueError(f"source_date for bundle artifact {artifact_rel} must be YYYY-MM-DD or unknown")
        item_id = manifest_text(item, "id", default=source_slug)
        if item_id in seen_item_ids:
            previous_artifact = seen_item_ids[item_id]
            raise ValueError(
                "bundle manifest item id "
                f"{item_id!r} is used by both {previous_artifact} and {artifact_rel}"
            )
        seen_item_ids[item_id] = artifact_rel

        prepared_items.append(
            {
                "artifact_rel": artifact_rel,
                "artifact_path": artifact_path,
                "artifact_hash": file_content_hash(artifact_path),
                "artifact_size_bytes": artifact_path.stat().st_size,
                "source_title": source_title,
                "source_slug": source_slug,
                "source_type": source_type,
                "original_url": original_url,
                "author": author,
                "source_date": source_date,
                "item_id": item_id,
                "bundle_item_index": bundle_item_index,
                "manifest_index": manifest_index,
                "evidence_title": manifest_optional_text(item, "evidence_title"),
                "evidence": manifest_optional_text(item, "evidence"),
                "evidence_slug": manifest_optional_text(item, "evidence_slug"),
            }
        )

    results: list[SourceCaptureResult] = []
    for item in prepared_items:
        source_metadata = {
            "import_pipeline": "source-bundle",
            "bundle_schema": SOURCE_BUNDLE_SCHEMA_KIND,
            "bundle_schema_version": schema_version,
            "bundle_id": bundle_id,
            "bundle_title": bundle_title,
            "bundle_path": bundle_root.as_posix(),
            "bundle_manifest_path": manifest_path.as_posix(),
            "bundle_manifest_hash": manifest_hash,
            "bundle_artifact_path": item["artifact_rel"],
            "bundle_artifact_hash": item["artifact_hash"],
            "bundle_artifact_size_bytes": item["artifact_size_bytes"],
            "bundle_item_id": item["item_id"],
            "bundle_item_index": item["bundle_item_index"],
            "bundle_manifest_index": item["manifest_index"],
        }
        result = capture_source(
            root,
            item["artifact_path"],
            item["source_title"],
            slug=item["source_slug"],
            source_type=item["source_type"],
            original_url=item["original_url"],
            author=item["author"],
            source_date=item["source_date"],
            today=today,
            allow_duplicate=allow_duplicates,
            source_metadata=source_metadata,
        )
        if create_evidence and result.note is not None:
            evidence = extract_evidence(
                root,
                result.note.note_id,
                title=item["evidence_title"],
                evidence=item["evidence"],
                slug=item["evidence_slug"],
                today=today,
            )
            result = SourceCaptureResult(
                status=result.status,
                source_file=result.source_file,
                title=result.title,
                content_hash=result.content_hash,
                note=result.note,
                raw_path=result.raw_path,
                evidence_note=evidence,
                existing_note_id=result.existing_note_id,
                existing_note_path=result.existing_note_path,
                reason=result.reason,
            )
        results.append(result)

    return SourceBundleImportResult(
        bundle_id=bundle_id,
        title=bundle_title,
        schema_version=schema_version,
        bundle_path=bundle_root,
        manifest_path=manifest_path,
        manifest_hash=manifest_hash,
        results=results,
    )


def capture_source(
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
    allow_duplicate: bool = False,
    source_metadata: dict[str, Any] | None = None,
) -> SourceCaptureResult:
    root = ensure_valid_vault(vault_path)
    source_path = Path(source_file).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"source file does not exist: {source_file}")
    if is_blank(title):
        raise ValueError("title must not be blank")
    if not is_date_like(source_date):
        raise ValueError("source_date must be YYYY-MM-DD or unknown")

    created_at = today or date.today().isoformat()
    content_hash = file_content_hash(source_path)
    if not allow_duplicate:
        existing = find_existing_source_by_content_hash(root, content_hash)
        if existing is not None:
            return SourceCaptureResult(
                status="skipped",
                source_file=source_path,
                title=title,
                content_hash=content_hash,
                existing_note_id=existing.noesis_id,
                existing_note_path=existing.path,
                reason="duplicate-content",
            )

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
        "content_hash": content_hash,
        "content_hash_algorithm": "sha256",
        "source_size_bytes": source_path.stat().st_size,
        "original_path": source_path.as_posix(),
        "tags": ["noesis", "source"],
        "aliases": [],
    }
    if source_metadata:
        metadata.update(validate_flat_source_metadata(source_metadata))
    body = f"""# {title}

Raw source: [{raw_name}](../raw/{raw_name})

## Summary

## Key Claims

## Evidence Candidates

## Open Questions
"""
    write_note_and_validate(root, note_path, metadata, body, cleanup_paths=[raw_target])
    return SourceCaptureResult(
        status="created",
        source_file=source_path,
        title=title,
        content_hash=content_hash,
        note=CreatedNote(note_id=note_id, path=note_path),
        raw_path=raw_target,
    )


def deterministic_source_paths(source_files: Sequence[Path | str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for source_file in source_files:
        path = Path(source_file).expanduser().resolve()
        if path in seen:
            continue
        if not path.is_file():
            raise ValueError(f"source file does not exist: {source_file}")
        paths.append(path)
        seen.add(path)
    return sorted(paths, key=lambda path: path.as_posix())


def title_from_source_path(source_path: Path, *, source_root: Path | None = None) -> str:
    rel = relative_source_path(source_path, source_root)
    stem = rel.with_suffix("").as_posix()
    return re.sub(r"[-_/]+", " ", stem).strip().title() or source_path.stem


def slug_from_source_path(source_path: Path, *, source_root: Path | None = None) -> str:
    rel = relative_source_path(source_path, source_root)
    return slugify(rel.with_suffix("").as_posix())


def relative_source_path(source_path: Path, source_root: Path | None) -> Path:
    if source_root is None:
        return Path(source_path.name)
    try:
        return source_path.relative_to(source_root)
    except ValueError:
        return Path(source_path.name)


def file_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def find_existing_source_by_content_hash(root: Path, content_hash: str) -> Note | None:
    vault = Vault.load(root)
    for note in sorted(vault.notes, key=lambda item: item.rel_path.as_posix()):
        if note.type != "source":
            continue
        if source_note_content_hash(note) == content_hash:
            return note
    return None


def source_note_content_hash(note: Note) -> str | None:
    content_hash = note.metadata.get("content_hash")
    if isinstance(content_hash, str) and content_hash.startswith("sha256:"):
        return content_hash

    raw_path = note.metadata.get("raw_path")
    if not isinstance(raw_path, str) or is_blank(raw_path):
        return None
    candidate = (note.path.parent / raw_path).resolve()
    if not candidate.is_file():
        return None
    return file_content_hash(candidate)


def resolve_bundle_manifest(bundle_path: Path | str, manifest_name: str) -> Path:
    path = Path(bundle_path).expanduser().resolve()
    if path.is_dir():
        manifest_path = path / manifest_name
    elif path.is_file():
        manifest_path = path
    else:
        raise ValueError(f"source bundle path does not exist: {bundle_path}")
    if not manifest_path.is_file():
        raise ValueError(f"source bundle manifest does not exist: {manifest_path}")
    return manifest_path.resolve()


def read_source_bundle_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid source bundle manifest YAML: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("source bundle manifest must be a YAML mapping")
    for key, value in manifest.items():
        if key not in SOURCE_BUNDLE_TOP_LEVEL_FIELDS:
            raise ValueError(f"bundle manifest field {key!r} is not part of source bundle schema v1")
        if key == "artifacts":
            continue
        if isinstance(value, (dict, list)):
            raise ValueError(f"bundle manifest field {key!r} must be a scalar value")
    return manifest


def source_bundle_schema_version(manifest: dict[str, Any]) -> str:
    schema_version = manifest_text(manifest, "schema_version", default=SOURCE_BUNDLE_SCHEMA_VERSION)
    if schema_version != SOURCE_BUNDLE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported source bundle schema_version "
            f"{schema_version!r}; expected {SOURCE_BUNDLE_SCHEMA_VERSION!r}"
        )
    return schema_version


def normalize_bundle_artifact(entry: Any, manifest_index: int) -> dict[str, Any]:
    if isinstance(entry, str):
        return {"path": entry}
    if not isinstance(entry, dict):
        raise ValueError(f"bundle artifact #{manifest_index} must be a path string or mapping")
    for key, value in entry.items():
        if key not in SOURCE_BUNDLE_ARTIFACT_FIELDS:
            raise ValueError(
                f"bundle artifact #{manifest_index} field {key!r} is not part of source bundle schema v1"
            )
        if isinstance(value, (dict, list)):
            raise ValueError(f"bundle artifact #{manifest_index} field {key!r} must be a scalar value")
    for key in SOURCE_BUNDLE_REQUIRED_ARTIFACT_FIELDS:
        manifest_text(entry, key)
    return entry


def resolve_bundle_artifact(bundle_root: Path, artifact_rel: Path) -> Path:
    if artifact_rel.is_absolute() or ".." in artifact_rel.parts:
        raise ValueError(f"bundle artifact path must stay inside the bundle: {artifact_rel.as_posix()}")
    artifact_path = (bundle_root / artifact_rel).resolve()
    try:
        artifact_path.relative_to(bundle_root)
    except ValueError as exc:
        raise ValueError(f"bundle artifact path must stay inside the bundle: {artifact_rel.as_posix()}") from exc
    if not artifact_path.is_file():
        raise ValueError(f"bundle artifact does not exist: {artifact_rel.as_posix()}")
    return artifact_path


def manifest_text(data: dict[str, Any], key: str, *, default: Any = None) -> str:
    value = data.get(key, default)
    if isinstance(value, date):
        value = value.isoformat()
    if value is None or is_blank(value):
        raise ValueError(f"bundle manifest field {key!r} must not be blank")
    if isinstance(value, (dict, list)):
        raise ValueError(f"bundle manifest field {key!r} must be a scalar value")
    return str(value)


def manifest_optional_text(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None or is_blank(value):
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        raise ValueError(f"bundle manifest field {key!r} must be a scalar value")
    return str(value)


def validate_flat_source_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, dict):
            raise ValueError(f"source metadata field {key!r} must be flat, not a mapping")
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            raise ValueError(f"source metadata field {key!r} must be flat, not nested")
        cleaned[str(key)] = value.isoformat() if isinstance(value, date) else value
    return cleaned


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
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")

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
    write_note_and_validate(root, note_path, metadata, body)
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
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")

    created_at = today or date.today().isoformat()
    note_title = title or f"Claim from {evidence_notes[0].title}"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"claim-{note_slug}")
    note_path = unique_note_path(root / "claims", f"{note_id}.md")
    source_links = sorted(collect_source_links(vault, evidence_notes))
    if not source_links:
        raise ValueError("claim evidence must link to at least one source note")
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
    write_note_and_validate(root, note_path, metadata, body)
    return CreatedNote(note_id=note_id, path=note_path)


def synthesize_claims(
    vault_path: Path | str,
    claim_refs: list[str],
    *,
    title: str | None = None,
    synthesis: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if not claim_refs:
        raise ValueError("at least one claim reference is required")
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    claims: list[Note] = []
    for ref in claim_refs:
        note = vault.find_note(ref)
        if note is None:
            raise ValueError(f"claim note not found: {ref}")
        if note.type != "claim":
            raise ValueError(f"claim reference is not a claim note: {ref}")
        if note.review_state == "changes-requested" or is_excluded(note):
            raise ValueError(f"claim is not ready for synthesis: {ref}")
        claims.append(note)
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")

    source_links = sorted(collect_relationship_links(vault, claims, "sources", expected_type="source"))
    evidence_links = sorted(collect_relationship_links(vault, claims, "evidence", expected_type="evidence"))
    if not source_links:
        raise ValueError("synthesis claims must link to at least one source note")
    if not evidence_links:
        raise ValueError("synthesis claims must link to at least one evidence note")

    created_at = today or date.today().isoformat()
    note_title = title or f"Synthesis from {claims[0].title}"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"synthesis-{note_slug}")
    note_path = unique_note_path(root / "syntheses", f"{note_id}.md")
    claim_links = [wikilink(note.noesis_id) for note in claims]
    metadata = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "synthesis",
        "lifecycle_stage": "synthesis",
        "status": "draft",
        "review_state": "ready-for-review",
        "confidence": "medium",
        "created": created_at,
        "updated": created_at,
        "sources": source_links,
        "evidence": evidence_links,
        "claims": claim_links,
        "tags": ["noesis", "synthesis"],
        "aliases": [],
    }
    synthesis_text = synthesis or "Review this draft and replace this placeholder with cross-claim synthesis."
    body = f"""# {note_title}

## Synthesis

{synthesis_text}

## Supporting Claims

{format_link_list(claim_links)}

## Tensions Or Gaps

## Implications
"""
    write_note_and_validate(root, note_path, metadata, body)
    return CreatedNote(note_id=note_id, path=note_path)


def approve_review(
    vault_path: Path | str,
    note_ref: str,
    *,
    reviewer: str = "unknown",
    basis: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    next_review: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    return write_review_decision(
        vault_path,
        note_ref,
        decision="approved",
        reviewer=reviewer,
        basis=basis,
        title=title,
        slug=slug,
        next_review=next_review,
        today=today,
    )


def request_review_changes(
    vault_path: Path | str,
    note_ref: str,
    *,
    reviewer: str = "unknown",
    basis: str | None = None,
    changes_requested: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    return write_review_decision(
        vault_path,
        note_ref,
        decision="changes-requested",
        reviewer=reviewer,
        basis=basis,
        changes_requested=changes_requested,
        title=title,
        slug=slug,
        today=today,
    )


def renew_review(
    vault_path: Path | str,
    note_ref: str,
    *,
    next_review: str | date,
    reviewer: str = "unknown",
    basis: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")
    parsed_next_review = parse_review_date(next_review)
    if parsed_next_review is None:
        raise ValueError("next_review must be YYYY-MM-DD")

    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    target = vault.find_note(note_ref)
    if target is None:
        raise ValueError(f"review target not found: {note_ref}")
    if target.type in {"dashboard", "review", "source", "archived-history"}:
        raise ValueError(f"note type cannot be renewed by this command: {target.type}")
    if target.type == "stale-memory":
        if not is_excluded(target):
            raise ValueError("stale-memory renewal requires stale, superseded, or archived status")
    elif target.review_state not in {"approved", "reviewed"} or is_excluded(target):
        raise ValueError("only current approved or reviewed notes can be renewed")

    renewed_at = today or date.today().isoformat()
    scheduled_for = parsed_next_review.isoformat()
    note_title = title or f"Scheduled Review - {target.title}"
    note_slug = slugify(slug or f"{target.noesis_id}-renewed")
    note_id = unique_noesis_id(root, f"review-{note_slug}")
    note_path = unique_note_path(root / "review", f"{note_id}.md")
    review_link = wikilink(note_id)
    target_link = wikilink(target.noesis_id)

    review_metadata: dict[str, Any] = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "review",
        "lifecycle_stage": "review",
        "status": "complete",
        "review_state": "approved",
        "confidence": "medium",
        "created": renewed_at,
        "updated": renewed_at,
        "reviewer": reviewer,
        "reviewed_at": renewed_at,
        "reviewed_notes": [target_link],
        "decision": "renewed",
        "next_review": scheduled_for,
        "tags": ["noesis", "review"],
        "aliases": [],
    }

    target_metadata = dict(target.metadata)
    target_metadata["updated"] = renewed_at
    target_metadata["reviewed_at"] = renewed_at
    target_metadata["next_review"] = scheduled_for
    if target.type == "stale-memory":
        target_metadata["review_state"] = "reviewed"
    add_relationship_link(target_metadata, "reviewed_by", review_link)

    basis_text = basis or "Scheduled lifecycle review confirmed the note remains fit for its current lifecycle role."
    body = f"""# {note_title}

## Decision

renewed

## Reviewed Note

- {target_link}

## Basis

{basis_text}

## Changes Requested

None.

## Next Review

{scheduled_for}
"""
    write_notes_and_validate(root, [(target.path, target_metadata, target.body), (note_path, review_metadata, body)])
    return CreatedNote(note_id=note_id, path=note_path)


def write_review_decision(
    vault_path: Path | str,
    note_ref: str,
    *,
    decision: str,
    reviewer: str,
    basis: str | None = None,
    changes_requested: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    next_review: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if decision not in {"approved", "changes-requested"}:
        raise ValueError("decision must be approved or changes-requested")
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")
    if next_review is not None and not is_date_like(next_review):
        raise ValueError("next_review must be YYYY-MM-DD or unknown")
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    target = vault.find_note(note_ref)
    if target is None:
        raise ValueError(f"review target not found: {note_ref}")
    if target.type in {"dashboard", "review", "source", "archived-history"}:
        raise ValueError(f"note type cannot be reviewed by this command: {target.type}")

    reviewed_at = today or date.today().isoformat()
    note_title = title or f"Review - {target.title}"
    note_slug = slugify(slug or f"{target.noesis_id}-{decision}")
    note_id = unique_noesis_id(root, f"review-{note_slug}")
    note_path = unique_note_path(root / "review", f"{note_id}.md")
    review_link = wikilink(note_id)
    target_link = wikilink(target.noesis_id)

    review_metadata: dict[str, Any] = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "review",
        "lifecycle_stage": "review",
        "status": "complete",
        "review_state": "approved",
        "confidence": "medium",
        "created": reviewed_at,
        "updated": reviewed_at,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reviewed_notes": [target_link],
        "decision": decision,
        "tags": ["noesis", "review"],
        "aliases": [],
    }
    if next_review:
        review_metadata["next_review"] = next_review

    target_metadata = dict(target.metadata)
    target_metadata["updated"] = reviewed_at
    if decision == "approved":
        if is_excluded(target) and target.type != "stale-memory":
            raise ValueError("stale, superseded, or archived memory cannot be approved")
        if target.type != "stale-memory":
            target_metadata["status"] = "reviewed"
        target_metadata["review_state"] = "approved"
        if next_review:
            target_metadata["next_review"] = next_review
    else:
        target_metadata["status"] = "needs-review"
        target_metadata["review_state"] = "changes-requested"
    add_relationship_link(target_metadata, "reviewed_by", review_link)

    basis_text = basis or "Reviewed against linked source, evidence, and lifecycle context."
    requested_changes_text = changes_requested or ("None." if decision == "approved" else "Changes requested before approval.")
    body = f"""# {note_title}

## Decision

{decision}

## Reviewed Note

- {target_link}

## Basis

{basis_text}

## Changes Requested

{requested_changes_text}

## Next Review

{next_review or "Not scheduled."}
"""
    writes = [
        (target.path, target_metadata, target.body),
        (note_path, review_metadata, body),
    ]
    if decision == "changes-requested":
        append_dependent_memory_review_changes(vault, target, reviewed_at, writes)
    write_notes_and_validate(root, writes)
    return CreatedNote(note_id=note_id, path=note_path)


def promote_synthesis(
    vault_path: Path | str,
    synthesis_ref: str,
    *,
    title: str | None = None,
    knowledge: str | None = None,
    slug: str | None = None,
    next_review: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")
    if next_review is not None and not is_date_like(next_review):
        raise ValueError("next_review must be YYYY-MM-DD or unknown")
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    synthesis_note = vault.find_note(synthesis_ref)
    if synthesis_note is None:
        raise ValueError(f"synthesis note not found: {synthesis_ref}")
    if synthesis_note.type != "synthesis":
        raise ValueError(f"synthesis reference is not a synthesis note: {synthesis_ref}")
    if synthesis_note.status != "reviewed" or synthesis_note.review_state != "approved":
        raise ValueError("synthesis must be approved before promotion")

    review_links = sorted(collect_relationship_links(vault, [synthesis_note], "reviewed_by", expected_type="review"))
    if not review_links:
        raise ValueError("synthesis must have a review audit note before promotion")

    claim_links = sorted(collect_relationship_links(vault, [synthesis_note], "claims", expected_type="claim"))
    evidence_links = sorted(collect_relationship_links(vault, [synthesis_note], "evidence", expected_type="evidence"))
    source_links = sorted(collect_relationship_links(vault, [synthesis_note], "sources", expected_type="source"))
    if not claim_links or not evidence_links or not source_links:
        raise ValueError("synthesis must preserve source, evidence, and claim lineage before promotion")
    for source_link in source_links:
        source_note = vault.find_note(source_link)
        if source_note is None or is_excluded(source_note):
            raise ValueError("synthesis source and evidence lineage must be current before knowledge promotion")
    for evidence_link in evidence_links:
        evidence_note = vault.find_note(evidence_link)
        if evidence_note is None or is_excluded(evidence_note):
            raise ValueError("synthesis source and evidence lineage must be current before knowledge promotion")
    for claim_link in claim_links:
        claim_note = vault.find_note(claim_link)
        if (
            claim_note is None
            or claim_note.review_state not in {"approved", "reviewed"}
            or claim_note.status != "reviewed"
            or is_excluded(claim_note)
        ):
            raise ValueError("synthesis claims must be approved before knowledge promotion")
    for evidence_link in evidence_links:
        evidence_note = vault.find_note(evidence_link)
        if (
            evidence_note is None
            or evidence_note.status != "reviewed"
            or evidence_note.review_state not in {"approved", "reviewed"}
        ):
            raise ValueError("synthesis evidence must be approved before knowledge promotion")

    reviewed_at = today or date.today().isoformat()
    note_title = title or f"Reviewed Knowledge - {synthesis_note.title}"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"reviewed-knowledge-{note_slug}")
    note_path = unique_note_path(root / "knowledge", f"{note_id}.md")
    metadata: dict[str, Any] = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "reviewed-knowledge",
        "lifecycle_stage": "knowledge",
        "status": "active",
        "review_state": "reviewed",
        "confidence": synthesis_note.metadata.get("confidence", "medium"),
        "created": reviewed_at,
        "updated": reviewed_at,
        "sources": source_links,
        "evidence": evidence_links,
        "claims": claim_links,
        "syntheses": [wikilink(synthesis_note.noesis_id)],
        "reviewed_by": review_links,
        "reviewed_at": reviewed_at,
        "tags": ["noesis", "knowledge"],
        "aliases": [],
    }
    if next_review:
        metadata["next_review"] = next_review

    knowledge_text = knowledge or "Use the approved synthesis as current reviewed knowledge."
    body = f"""# {note_title}

## Current Knowledge

{knowledge_text}

## Why It Is Trusted

- Synthesis: {wikilink(synthesis_note.noesis_id)}
- Review: {format_inline_links(review_links)}

## Use In Future Work

Use this only while it remains current reviewed knowledge.

## Staleness Rule

Recheck this note when its source, evidence, claims, or synthesis are superseded.
"""
    write_note_and_validate(root, note_path, metadata, body)
    return CreatedNote(note_id=note_id, path=note_path)


def mark_memory_stale(
    vault_path: Path | str,
    note_ref: str,
    *,
    reason: str,
    superseded_by: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if is_blank(reason):
        raise ValueError("reason must not be blank")
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    target = vault.find_note(note_ref)
    if target is None:
        raise ValueError(f"memory note not found: {note_ref}")
    if target.type in {"dashboard", "review", "stale-memory", "archived-history"}:
        raise ValueError(f"note type cannot be marked stale by this command: {target.type}")

    superseding_note = None
    if superseded_by:
        superseding_note = vault.find_note(superseded_by)
        if superseding_note is None:
            raise ValueError(f"superseding note not found: {superseded_by}")

    marked_at = today or date.today().isoformat()
    status = "superseded" if superseding_note else "stale"
    note_title = title or f"Stale Memory - {target.title}"
    note_slug = slugify(slug or target.noesis_id)
    note_id = unique_noesis_id(root, f"stale-{note_slug}")
    note_path = unique_note_path(root / "stale", f"{note_id}.md")
    target_link = wikilink(target.noesis_id)
    superseded_by_links = [wikilink(superseding_note.noesis_id)] if superseding_note else []

    stale_metadata: dict[str, Any] = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "stale-memory",
        "lifecycle_stage": "stale",
        "status": status,
        "review_state": "reviewed",
        "confidence": target.metadata.get("confidence", "medium"),
        "created": marked_at,
        "updated": marked_at,
        "supersedes": [target_link],
        "tags": ["noesis", "stale"],
        "aliases": [],
    }
    if superseded_by_links:
        stale_metadata["superseded_by"] = superseded_by_links

    target_metadata = dict(target.metadata)
    target_metadata["status"] = status
    target_metadata["review_state"] = "reviewed"
    target_metadata["updated"] = marked_at
    if superseded_by_links:
        add_relationship_link(target_metadata, "superseded_by", superseded_by_links[0])

    writes: list[tuple[Path, dict[str, Any], str]] = [(target.path, target_metadata, target.body)]
    dependent_knowledge = [
        note
        for note in vault.current_reviewed_knowledge()
        if note.noesis_id != target.noesis_id and note_references_memory(vault, note, target.noesis_id)
    ]
    dependent_links = [wikilink(note.noesis_id) for note in dependent_knowledge]
    for note in dependent_knowledge:
        note_metadata = dict(note.metadata)
        note_metadata["status"] = status
        note_metadata["review_state"] = "reviewed"
        note_metadata["updated"] = marked_at
        if superseded_by_links:
            add_relationship_link(note_metadata, "superseded_by", superseded_by_links[0])
        writes.append((note.path, note_metadata, note.body))

    stale_body = f"""# {note_title}

## Stale Or Superseded Memory

- Supersedes: {target_link}
- Superseded by: {format_inline_links(superseded_by_links) if superseded_by_links else "None"}

## Reason

{reason}

## Traceability

Keep this note so future context builders can explain why {target_link} no longer guides active work.
"""
    writes.append((note_path, stale_metadata, stale_body))

    stale_link = wikilink(note_id)
    for context_note in vault.notes:
        if context_note.type != "operational-context":
            continue
        if not context_references_memory(vault, context_note, target.noesis_id):
            continue
        context_metadata = dict(context_note.metadata)
        remaining_knowledge = remaining_context_knowledge(vault, context_metadata, target.noesis_id)
        context_metadata["reviewed_knowledge"] = [wikilink(note.noesis_id) for note in remaining_knowledge]
        context_metadata["syntheses"] = sorted(
            collect_relationship_links(vault, remaining_knowledge, "syntheses", expected_type="synthesis")
        )
        remove_relationship_link(vault, context_metadata, "syntheses", target.noesis_id)
        add_relationship_link(context_metadata, "excluded_memory", target_link)
        for dependent_link in dependent_links:
            add_relationship_link(context_metadata, "excluded_memory", dependent_link)
        add_relationship_link(context_metadata, "excluded_memory", stale_link)
        context_metadata["updated"] = marked_at
        context_body = build_context_body(
            vault,
            remaining_knowledge,
            sorted(str(link) for link in as_list(context_metadata.get("excluded_memory"))),
            scope=context_scope(context_note),
            purpose=context_purpose(context_note),
        )
        writes.append((context_note.path, context_metadata, context_body))

    write_notes_and_validate(root, writes)
    return CreatedNote(note_id=note_id, path=note_path)


def write_context_note(
    vault_path: Path | str,
    *,
    scope: str | None = None,
    purpose: str | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    title: str | None = None,
    slug: str | None = None,
    next_review: str | None = None,
    today: str | None = None,
) -> CreatedNote:
    if title is not None and is_blank(title):
        raise ValueError("title must not be blank")
    if next_review is not None and not is_date_like(next_review):
        raise ValueError("next_review must be YYYY-MM-DD or unknown")
    validate_context_budget(limit=limit, max_chars=max_chars)
    root = ensure_valid_vault(vault_path)
    vault = Vault.load(root)
    package = compose_context(
        vault,
        scope=scope,
        purpose=purpose,
        limit=limit,
        max_chars=max_chars,
        profile=profile,
    )
    knowledge = package.reviewed_knowledge
    if not knowledge:
        raise ValueError("no current reviewed knowledge found for context")

    created_at = today or date.today().isoformat()
    note_title = title or "Noesis Operational Context"
    note_slug = slugify(slug or note_title)
    note_id = unique_noesis_id(root, f"context-{note_slug}")
    note_path = unique_note_path(root / "context", f"{note_id}.md")
    reviewed_knowledge_links = [wikilink(note.noesis_id) for note in knowledge]
    synthesis_links = sorted(collect_relationship_links(vault, knowledge, "syntheses", expected_type="synthesis"))
    excluded_links = sorted(wikilink(note.noesis_id) for note in vault.notes if is_excluded(note))
    metadata: dict[str, Any] = {
        "title": note_title,
        "noesis_id": note_id,
        "type": "operational-context",
        "lifecycle_stage": "context",
        "status": "active",
        "review_state": "reviewed",
        "confidence": "medium",
        "created": created_at,
        "updated": created_at,
        "syntheses": synthesis_links,
        "reviewed_knowledge": reviewed_knowledge_links,
        "excluded_memory": excluded_links,
        "tags": ["noesis", "context"],
        "aliases": [],
    }
    if next_review:
        metadata["next_review"] = next_review
    if scope:
        metadata["scope"] = scope
    if purpose:
        metadata["purpose"] = purpose
    if package.profile is not None:
        metadata["context_profile"] = package.profile
    if package.limit is not None:
        metadata["context_limit"] = package.limit
    if package.max_chars is not None:
        metadata["context_max_chars"] = package.max_chars

    body = package.content
    body = body.rstrip() + "\n\n## Traceability\n\n"
    body += f"- Reviewed knowledge: {format_inline_links(reviewed_knowledge_links)}\n"
    if synthesis_links:
        body += f"- Syntheses: {format_inline_links(synthesis_links)}\n"
    if excluded_links:
        body += f"- Excluded memory: {format_inline_links(excluded_links)}\n"

    write_note_and_validate(root, note_path, metadata, body)
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

Use these read-only inspection commands from the repo root when a row needs
closer inspection:

```bash
PYTHONPATH=src python -m noesis review summary --vault <vault-path>
PYTHONPATH=src python -m noesis review queue --vault <vault-path> --due --due-on {today}
PYTHONPATH=src python -m noesis review show <note-id> --vault <vault-path>
```

`review summary`, `review queue`, and `review show` report overdue review
status, audit gaps, requested changes, downstream reviewed-knowledge/context
impact, and complete lineage.

Use this write action after a scheduled review confirms the note still fits
its current lifecycle role:

```bash
PYTHONPATH=src python -m noesis review renew <note-id> --vault <vault-path> --next-review <YYYY-MM-DD>
```

`review renew` records the scheduled review audit and moves `next_review`
without changing active, stale, or superseded lifecycle status.

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
    name: Audit trail gaps
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
        - excluded_memory != null || superseded_by != null || status == "stale" || status == "archived" || lifecycle_stage == "archive"
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


def build_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
) -> str:
    return compose_context(
        vault,
        scope=scope,
        purpose=purpose,
        limit=limit,
        max_chars=max_chars,
        profile=profile,
    ).content


def compose_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
) -> ContextPackage:
    validate_context_budget(limit=limit, max_chars=max_chars)
    profile_definition = resolve_context_profile(profile)
    effective_limit, effective_max_chars, applied_profile_defaults = apply_context_profile_defaults(
        profile_definition,
        limit=limit,
        max_chars=max_chars,
    )
    validate_context_budget(limit=effective_limit, max_chars=effective_max_chars)
    available = vault.current_reviewed_knowledge()
    selected, scoped_out = select_knowledge_for_context(
        available,
        scope,
        profile=profile_definition,
        applied_profile_defaults=applied_profile_defaults,
    )
    included, budgeted_out = apply_context_budget(
        selected,
        limit=effective_limit,
        max_chars=effective_max_chars,
    )
    excluded = sorted(
        scoped_out + budgeted_out,
        key=lambda selection: (selection.status, selection.note.title.lower()),
    )
    lifecycle_excluded = explain_lifecycle_exclusions(vault)
    lineage_summaries = [context_lineage_summary(vault, selection.note) for selection in included]
    handoff = context_handoff_guidance(
        vault_path=vault.root,
        scope=scope,
        purpose=purpose,
        profile=profile_definition,
        limit=effective_limit,
        max_chars=effective_max_chars,
        included=included,
        excluded=excluded,
        lifecycle_excluded=lifecycle_excluded,
    )
    if profile_definition is not None and profile_definition.name == "codex-handoff":
        content = render_context_handoff(
            included,
            lineage_summaries,
            lifecycle_excluded,
            handoff,
            scope=scope,
            profile=profile_definition,
            limit=effective_limit,
            max_chars=effective_max_chars,
            total_candidates=len(available),
            excluded=excluded,
        )
    else:
        content = render_context(
            [selection.note for selection in included],
            scope=scope,
            purpose=purpose,
            profile=profile_definition,
            limit=effective_limit,
            max_chars=effective_max_chars,
            total_candidates=len(available),
            excluded=excluded,
        )
    return ContextPackage(
        profile=profile_definition.name if profile_definition else None,
        profile_description=profile_definition.description if profile_definition else None,
        scope=scope,
        purpose=purpose,
        limit=effective_limit,
        max_chars=effective_max_chars,
        requested_limit=limit,
        requested_max_chars=max_chars,
        applied_profile_defaults=applied_profile_defaults,
        available_count=len(available),
        included=included,
        excluded=excluded,
        scoped_out=scoped_out,
        budgeted_out=budgeted_out,
        lifecycle_excluded=lifecycle_excluded,
        lineage_summaries=lineage_summaries,
        handoff=handoff,
        content=content,
    )


def validate_context_budget(*, limit: int | None = None, max_chars: int | None = None) -> None:
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")
    if max_chars is not None and max_chars < 1:
        raise ValueError("max_chars must be greater than zero")


def resolve_context_profile(profile: str | None) -> ContextProfile | None:
    if profile is None or not profile.strip():
        return None
    key = profile.strip().lower()
    profile_definition = CONTEXT_PROFILES.get(key)
    if profile_definition is None:
        expected = ", ".join(sorted(CONTEXT_PROFILE_NAMES))
        raise ValueError(f"profile must be one of: {expected}")
    return profile_definition


def apply_context_profile_defaults(
    profile: ContextProfile | None,
    *,
    limit: int | None,
    max_chars: int | None,
) -> tuple[int | None, int | None, tuple[str, ...]]:
    if profile is None:
        return limit, max_chars, ()
    applied: list[str] = []
    effective_limit = limit
    effective_max_chars = max_chars
    if effective_limit is None and profile.default_limit is not None:
        effective_limit = profile.default_limit
        applied.append("limit")
    if effective_max_chars is None and profile.default_max_chars is not None:
        effective_max_chars = profile.default_max_chars
        applied.append("max_chars")
    return effective_limit, effective_max_chars, tuple(applied)


def select_knowledge_for_context(
    knowledge: list[Note],
    scope: str | None,
    *,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> tuple[list[ContextSelection], list[ContextSelection]]:
    scope_terms = context_scope_terms(scope)
    selected: list[ContextSelection] = []
    scoped_out: list[ContextSelection] = []
    for note in knowledge:
        score = context_scope_score(note, scope_terms)
        selection = ContextSelection(
            note=note,
            status="included",
            reason=context_include_reason(scope, score, profile, applied_profile_defaults),
            score=score,
            content_chars=len(note.body.strip()),
        )
        if scope_terms and score == 0:
            scoped_out.append(
                ContextSelection(
                    note=note,
                    status="scoped_out",
                    reason=context_scoped_out_reason(scope, profile, applied_profile_defaults),
                    score=score,
                    content_chars=selection.content_chars,
                )
            )
        else:
            selected.append(selection)
    selected.sort(key=lambda selection: (-selection.score, selection.note.title.lower()))
    return selected, scoped_out


def apply_context_budget(
    selections: list[ContextSelection],
    *,
    limit: int | None = None,
    max_chars: int | None = None,
) -> tuple[list[ContextSelection], list[ContextSelection]]:
    included: list[ContextSelection] = []
    budgeted_out: list[ContextSelection] = []
    used_chars = 0
    for index, selection in enumerate(selections):
        if limit is not None and len(included) >= limit:
            budgeted_out.extend(
                ContextSelection(
                    note=remaining.note,
                    status="budgeted_out",
                    reason=f"excluded by limit {limit}",
                    score=remaining.score,
                    content_chars=remaining.content_chars,
                )
                for remaining in selections[index:]
            )
            break
        if max_chars is not None and used_chars + selection.content_chars > max_chars:
            remaining_chars = max(max_chars - used_chars, 0)
            budgeted_out.append(
                ContextSelection(
                    note=selection.note,
                    status="budgeted_out",
                    reason=(
                        f"excluded by max_chars {max_chars}: "
                        f"{selection.content_chars} chars exceeds remaining budget {remaining_chars}"
                    ),
                    score=selection.score,
                    content_chars=selection.content_chars,
                )
            )
            continue
        included.append(selection)
        used_chars += selection.content_chars
    return included, budgeted_out


def context_scope_terms(scope: str | None) -> list[str]:
    if scope is None or not scope.strip():
        return []
    return [term for term in re.split(r"[\s,]+", scope.strip().lower()) if term]


def context_scope_score(note: Note, scope_terms: list[str]) -> int:
    if not scope_terms:
        return 0
    searchable = searchable_note_text(note)
    return sum(1 for term in scope_terms if term in searchable)


def context_include_reason(
    scope: str | None,
    score: int,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    if scope is None or not scope.strip():
        reason = "included because no scope filter was requested"
    else:
        reason = f"matches scope {scope!r} with score {score}"
    reason += context_profile_reason_suffix(profile, applied_profile_defaults)
    return reason


def context_scoped_out_reason(
    scope: str | None,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    reason = f"does not match scope {scope!r}"
    reason += context_profile_reason_suffix(profile, applied_profile_defaults)
    return reason


def context_profile_reason_suffix(
    profile: ContextProfile | None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    if profile is None:
        return ""
    if applied_profile_defaults:
        defaults = ", ".join(applied_profile_defaults)
        return f"; profile {profile.name!r} supplied context defaults: {defaults}"
    return f"; profile {profile.name!r} selected with explicit context budgets"


def explain_lifecycle_exclusions(vault: Vault) -> list[ContextSelection]:
    selections: list[ContextSelection] = []
    for note in vault.notes:
        if not is_excluded(note):
            continue
        selections.append(
            ContextSelection(
                note=note,
                status="lifecycle_excluded",
                reason=(
                    f"{note.type} has status {note.status!r} "
                    f"and lifecycle_stage {note.lifecycle_stage!r}; "
                    f"intentionally excluded as {context_lifecycle_exclusion_kind(note)} note"
                ),
                score=0,
                content_chars=len(note.body.strip()),
            )
        )
    return sorted(selections, key=lambda selection: selection.note.title.lower())


def context_lifecycle_exclusion_kind(note: Note) -> str:
    if note.lifecycle_stage == "archive" or note.status == "archived":
        return "archived"
    if note.status == "superseded":
        return "superseded"
    if note.status == "stale":
        return "stale"
    return "excluded"


def context_lineage_summary(vault: Vault, note: Note) -> ContextLineageSummary:
    return ContextLineageSummary(
        reviewed_knowledge=note,
        sources=context_relationship_notes(vault, note, "sources", expected_type="source"),
        evidence=context_relationship_notes(vault, note, "evidence", expected_type="evidence"),
        claims=context_relationship_notes(vault, note, "claims", expected_type="claim"),
        syntheses=context_relationship_notes(vault, note, "syntheses", expected_type="synthesis"),
        reviews=context_relationship_notes(vault, note, "reviewed_by", expected_type="review"),
    )


def context_relationship_notes(
    vault: Vault,
    note: Note,
    key: str,
    *,
    expected_type: str | None = None,
) -> list[Note]:
    notes_by_id: dict[str, Note] = {}
    for item in as_list(note.metadata.get(key)):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            target_note = vault.find_note(target)
            if target_note is None:
                continue
            if expected_type is not None and target_note.type != expected_type:
                continue
            notes_by_id[target_note.noesis_id] = target_note
    return sorted(notes_by_id.values(), key=lambda item: item.rel_path.as_posix())


def context_handoff_guidance(
    *,
    vault_path: Path,
    scope: str | None,
    purpose: str | None,
    profile: ContextProfile | None,
    limit: int | None,
    max_chars: int | None,
    included: list[ContextSelection],
    excluded: list[ContextSelection],
    lifecycle_excluded: list[ContextSelection],
) -> ContextHandoffGuidance:
    vault_flag = f" --vault {shell_quote(str(vault_path))}"
    scope_flag = f" --scope {shell_quote(scope)}" if scope else ""
    purpose_flag = f" --purpose {shell_quote(purpose)}" if purpose else ""
    profile_flag = f" --profile {profile.name}" if profile is not None else ""
    limit_flag = f" --limit {limit}" if limit is not None else ""
    max_chars_flag = f" --max-chars {max_chars}" if max_chars is not None else ""
    task_purpose = purpose or "Continue the task using the selected current reviewed knowledge."
    assumptions = [
        "Active guidance is limited to current reviewed knowledge selected for this package.",
        (
            "Stale, superseded, and archived notes are exclusion provenance only "
            "and must not be treated as active instructions."
        ),
    ]
    if scope:
        assumptions.append(
            f"The requested scope is {scope!r}; "
            "scoped-out reviewed notes need a separate handoff if they matter."
        )
    if excluded:
        assumptions.append(
            "Some current reviewed notes were omitted by scope or budget; "
            "inspect selection provenance before widening work."
        )
    if lifecycle_excluded:
        assumptions.append(
            "Lifecycle-excluded memory remains traceable for audit but is excluded from active context."
        )

    validation_commands = [
        "git diff --check",
        f"PYTHONPATH=src python -m noesis vault doctor {shell_quote(str(vault_path))} --json",
        (
            "PYTHONPATH=src python -m noesis context build"
            f"{vault_flag}"
            f"{scope_flag}{purpose_flag}{profile_flag}{limit_flag}{max_chars_flag} --json"
        ),
        (
            "PYTHONPATH=src python -m noesis context explain"
            f"{vault_flag}"
            f"{scope_flag}{purpose_flag}{profile_flag}{limit_flag}{max_chars_flag} --json"
        ),
        "PYTHONPATH=src python -m unittest discover -s tests -v",
    ]
    next_steps = [
        "Use the selected reviewed knowledge as the active task brief.",
        "Check the lineage summaries before changing source-backed claims or syntheses.",
        "Keep lifecycle-excluded notes out of active guidance unless they are renewed through review.",
        "Run the validation commands before handing work back.",
    ]
    if included:
        selected = ", ".join(selection.note.noesis_id for selection in included)
        next_steps.insert(1, f"Start from selected reviewed knowledge: {selected}.")
    return ContextHandoffGuidance(
        task_purpose=task_purpose,
        assumptions=assumptions,
        validation_commands=validation_commands,
        next_steps=next_steps,
    )


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def context_lifecycle_exclusion_counts(selections: list[ContextSelection]) -> dict[str, int]:
    summary = {"stale": 0, "superseded": 0, "archived": 0, "excluded": 0}
    for selection in selections:
        kind = context_lifecycle_exclusion_kind(selection.note)
        summary[kind] = summary.get(kind, 0) + 1
    return summary


def render_context_handoff(
    included: list[ContextSelection],
    lineage_summaries: list[ContextLineageSummary],
    lifecycle_excluded: list[ContextSelection],
    handoff: ContextHandoffGuidance,
    *,
    scope: str | None = None,
    profile: ContextProfile | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    total_candidates: int | None = None,
    excluded: list[ContextSelection] | None = None,
) -> str:
    lines = ["# Noesis Codex Handoff Pack", ""]
    if scope:
        lines.extend([f"Scope: {scope}", ""])
    lines.extend([f"Purpose: {handoff.task_purpose}", ""])
    if profile is not None:
        lines.extend([f"Profile: {profile.name}", ""])
    if limit is not None or max_chars is not None:
        budget = []
        if limit is not None:
            budget.append(f"limit {limit}")
        if max_chars is not None:
            budget.append(f"max_chars {max_chars}")
        lines.extend([f"Budget: {', '.join(budget)}", ""])
    lines.extend(
        [
            "Active guidance in this pack is built from current reviewed knowledge only.",
            "Stale, superseded, and archived memory is listed only as excluded provenance.",
            "",
            "## Task Purpose",
            "",
            handoff.task_purpose,
            "",
            "## Active Reviewed Knowledge",
            "",
        ]
    )
    if included:
        for selection in included:
            note = selection.note
            lines.extend(
                [
                    f"### {note.title}",
                    "",
                    f"- noesis_id: {note.noesis_id}",
                    f"- path: {note.rel_path.as_posix()}",
                    f"- confidence: {note.metadata.get('confidence', 'unknown')}",
                    f"- reviewed_at: {note.metadata.get('reviewed_at', 'unknown')}",
                    f"- selection_reason: {selection.reason}",
                    "",
                    note.body.strip(),
                    "",
                ]
            )
    else:
        lines.extend(["No current reviewed knowledge selected.", ""])

    lines.extend(["## Selection Provenance", ""])
    available_count = total_candidates if total_candidates is not None else len(included)
    lines.append(f"- Current reviewed knowledge available: {available_count}")
    lines.append(f"- Included in active handoff: {len(included)}")
    lines.append(f"- Excluded by scope or budget: {len(excluded or [])}")
    lines.append("")
    for selection in included:
        lines.append(format_handoff_selection(selection))
    if excluded:
        for selection in excluded:
            lines.append(format_handoff_selection(selection))
    if not included and not excluded:
        lines.append("No selection provenance available.")

    lines.extend(["", "## Relevant Lineage", ""])
    if lineage_summaries:
        for summary in lineage_summaries:
            lines.append(format_handoff_lineage(summary))
    else:
        lines.append("No included reviewed knowledge lineage to summarize.")

    lines.extend(["", "## Lifecycle Exclusions", ""])
    summary = context_lifecycle_exclusion_counts(lifecycle_excluded)
    lines.append(
        "Summary: "
        f"stale={summary['stale']}, "
        f"superseded={summary['superseded']}, "
        f"archived={summary['archived']}, "
        f"other={summary['excluded']}"
    )
    lines.append("")
    if lifecycle_excluded:
        for selection in lifecycle_excluded:
            lines.append(format_handoff_selection(selection))
    else:
        lines.append("No stale, superseded, or archived reviewed memory found.")

    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {assumption}" for assumption in handoff.assumptions)
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{command}`" for command in handoff.validation_commands)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {step}" for step in handoff.next_steps)
    return "\n".join(lines).rstrip() + "\n"


def format_handoff_selection(selection: ContextSelection) -> str:
    suffix = ""
    if selection.status == "lifecycle_excluded":
        suffix = f", kind={context_lifecycle_exclusion_kind(selection.note)}"
    return (
        f"- {selection.note.noesis_id} ({selection.status}{suffix}, score={selection.score}, "
        f"chars={selection.content_chars}) - {selection.reason}; path: {selection.note.rel_path.as_posix()}"
    )


def format_handoff_lineage(summary: ContextLineageSummary) -> str:
    parts = [
        f"sources={format_handoff_note_ids(summary.sources)}",
        f"evidence={format_handoff_note_ids(summary.evidence)}",
        f"claims={format_handoff_note_ids(summary.claims)}",
        f"syntheses={format_handoff_note_ids(summary.syntheses)}",
        f"reviews={format_handoff_note_ids(summary.reviews)}",
    ]
    return f"- {summary.reviewed_knowledge.noesis_id}: " + "; ".join(parts)


def format_handoff_note_ids(notes: list[Note]) -> str:
    return ", ".join(note.noesis_id for note in notes) if notes else "none"


def render_context(
    knowledge: list[Note],
    scope: str | None = None,
    purpose: str | None = None,
    *,
    profile: ContextProfile | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    total_candidates: int | None = None,
    excluded: list[ContextSelection] | None = None,
) -> str:
    title = "Noesis Operational Context"
    lines = [f"# {title}", ""]
    if scope:
        lines.extend([f"Scope: {scope}", ""])
    if purpose:
        lines.extend([f"Purpose: {purpose}", ""])
    if profile is not None:
        lines.extend([f"Profile: {profile.name}", ""])
    if limit is not None or max_chars is not None:
        budget = []
        if limit is not None:
            budget.append(f"limit {limit}")
        if max_chars is not None:
            budget.append(f"max_chars {max_chars}")
        lines.extend([f"Budget: {', '.join(budget)}", ""])
    lines.extend(
        [
            "This context package is built from reviewed knowledge only.",
            "Stale, superseded, and archived memory is excluded.",
            "",
        ]
    )

    if total_candidates is not None or excluded:
        lines.extend(["## Selection Summary", ""])
        lines.append(f"- Current reviewed knowledge available: {total_candidates if total_candidates is not None else len(knowledge)}")
        lines.append(f"- Included in active context: {len(knowledge)}")
        if excluded:
            lines.append(f"- Excluded by scope or budget: {len(excluded)}")
        lines.append("")

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


def build_context_body(
    vault: Vault,
    knowledge: list[Note],
    excluded_links: list[str],
    *,
    scope: str | None = None,
    purpose: str | None = None,
) -> str:
    reviewed_knowledge_links = [wikilink(note.noesis_id) for note in knowledge]
    synthesis_links = sorted(collect_relationship_links(vault, knowledge, "syntheses", expected_type="synthesis"))
    body = render_context(knowledge, scope=scope, purpose=purpose).rstrip() + "\n\n## Traceability\n\n"
    body += f"- Reviewed knowledge: {format_inline_links(reviewed_knowledge_links)}\n"
    if synthesis_links:
        body += f"- Syntheses: {format_inline_links(synthesis_links)}\n"
    if excluded_links:
        body += f"- Excluded memory: {format_inline_links(excluded_links)}\n"
    return body


def append_dependent_memory_review_changes(
    vault: Vault,
    target: Note,
    reviewed_at: str,
    writes: list[tuple[Path, dict[str, Any], str]],
) -> None:
    dependent_knowledge = [
        note
        for note in vault.current_reviewed_knowledge()
        if note.noesis_id != target.noesis_id and note_references_memory(vault, note, target.noesis_id)
    ]
    for note in dependent_knowledge:
        note_metadata = dict(note.metadata)
        note_metadata["status"] = "needs-review"
        note_metadata["review_state"] = "changes-requested"
        note_metadata["updated"] = reviewed_at
        writes.append((note.path, note_metadata, note.body))

    for context_note in vault.notes:
        if context_note.type != "operational-context":
            continue
        if not context_references_memory(vault, context_note, target.noesis_id):
            continue
        context_metadata = dict(context_note.metadata)
        remaining_knowledge = remaining_context_knowledge(vault, context_metadata, target.noesis_id)
        context_metadata["reviewed_knowledge"] = [wikilink(note.noesis_id) for note in remaining_knowledge]
        context_metadata["syntheses"] = sorted(
            collect_relationship_links(vault, remaining_knowledge, "syntheses", expected_type="synthesis")
        )
        remove_relationship_link(vault, context_metadata, "syntheses", target.noesis_id)
        context_metadata["updated"] = reviewed_at
        context_body = build_context_body(
            vault,
            remaining_knowledge,
            sorted(str(link) for link in as_list(context_metadata.get("excluded_memory"))),
            scope=context_scope(context_note),
            purpose=context_purpose(context_note),
        )
        writes.append((context_note.path, context_metadata, context_body))


def context_scope(context_note: Note) -> str | None:
    scope = context_note.metadata.get("scope")
    if isinstance(scope, str) and not is_blank(scope):
        return scope
    return context_body_field(context_note, "Scope")


def context_purpose(context_note: Note) -> str | None:
    purpose = context_note.metadata.get("purpose")
    if isinstance(purpose, str) and not is_blank(purpose):
        return purpose
    return context_body_field(context_note, "Purpose")


def context_body_field(context_note: Note, label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(context_note.body)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def context_references_memory(vault: Vault, context_note: Note, target_noesis_id: str) -> bool:
    if relationship_contains(vault, context_note.metadata, "reviewed_knowledge", target_noesis_id):
        return True
    if relationship_contains(vault, context_note.metadata, "syntheses", target_noesis_id):
        return True
    return any(
        note_references_memory(vault, knowledge_note, target_noesis_id)
        for knowledge_note in context_reviewed_knowledge(vault, context_note.metadata)
    )


def remaining_context_knowledge(
    vault: Vault,
    context_metadata: dict[str, Any],
    stale_noesis_id: str,
) -> list[Note]:
    return [
        note
        for note in context_reviewed_knowledge(vault, context_metadata)
        if not note_references_memory(vault, note, stale_noesis_id)
    ]


def context_reviewed_knowledge(vault: Vault, context_metadata: dict[str, Any]) -> list[Note]:
    notes: list[Note] = []
    seen: set[str] = set()
    for item in as_list(context_metadata.get("reviewed_knowledge")):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            note = vault.find_note(target)
            if note is None or note.noesis_id in seen:
                continue
            if (
                note.type == "reviewed-knowledge"
                and note.lifecycle_stage == "knowledge"
                and note.review_state in {"reviewed", "approved"}
                and note.status in CURRENT_KNOWLEDGE_STATUSES
                and not is_excluded(note)
            ):
                notes.append(note)
                seen.add(note.noesis_id)
    return notes


def note_references_memory(vault: Vault, note: Note, target_noesis_id: str) -> bool:
    if note.noesis_id == target_noesis_id:
        return True
    for target in iter_metadata_wikilinks(note.metadata):
        target_note = vault.find_note(target)
        if target_note is not None and target_note.noesis_id == target_noesis_id:
            return True
    return False


def filter_knowledge_by_scope(knowledge: list[Note], scope: str | None) -> list[Note]:
    scope_terms = context_scope_terms(scope)
    if not scope_terms:
        return knowledge
    return [note for note in knowledge if context_scope_score(note, scope_terms) > 0]


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


def review_requires_audit(note: Note) -> bool:
    return note.type in {"evidence", "claim", "synthesis", "reviewed-knowledge"} and note.review_state in {
        "approved",
        "reviewed",
    }


def sort_review_notes(notes: Iterable[Note]) -> list[Note]:
    return sorted(
        notes,
        key=lambda note: (
            review_date_sort_key(note.metadata.get("next_review")),
            note.lifecycle_stage,
            note.title.lower(),
            note.rel_path.as_posix(),
        ),
    )


def review_date_sort_key(value: Any) -> tuple[int, str]:
    parsed = parse_review_date(value)
    if parsed is None:
        return (1, "")
    return (0, parsed.isoformat())


def note_review_due(note: Note, *, due_on: str | date | None = None) -> bool:
    cutoff = review_cutoff_date(due_on)
    next_review = parse_review_date(note.metadata.get("next_review"))
    if next_review is None:
        return False
    return next_review <= cutoff


def review_cutoff_date(value: str | date | None) -> date:
    if value is None:
        return date.today()
    parsed = parse_review_date(value)
    if parsed is None:
        raise ValueError("due_on must be YYYY-MM-DD")
    return parsed


def parse_review_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def write_note(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=False)
    path.write_text(f"---\n{frontmatter}---\n\n{body.rstrip()}\n", encoding="utf-8")


def write_note_and_validate(
    root: Path,
    path: Path,
    metadata: dict[str, Any],
    body: str,
    *,
    cleanup_paths: list[Path] | None = None,
) -> None:
    write_note(path, metadata, body)
    try:
        ensure_valid_vault(root)
    except ValueError:
        path.unlink(missing_ok=True)
        for cleanup_path in cleanup_paths or []:
            cleanup_path.unlink(missing_ok=True)
        raise


def write_notes_and_validate(root: Path, writes: list[tuple[Path, dict[str, Any], str]]) -> None:
    original_text: dict[Path, str | None] = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path, _, _ in writes
    }
    try:
        for path, metadata, body in writes:
            write_note(path, metadata, body)
        ensure_valid_vault(root)
    except ValueError:
        for path, text in original_text.items():
            if text is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(text, encoding="utf-8")
        raise


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def wikilink(target: str) -> str:
    return f"[[{target}]]"


def format_link_list(links: list[str]) -> str:
    if not links:
        return ""
    return "\n".join(f"- {link}" for link in links)


def format_inline_links(links: list[str]) -> str:
    return ", ".join(links) if links else "None"


def collect_source_links(vault: Vault, notes: list[Note]) -> set[str]:
    links: set[str] = set()
    for note in notes:
        for target in iter_metadata_wikilinks(note.metadata):
            target_note = vault.find_note(target)
            if target_note is not None and target_note.type == "source":
                links.add(wikilink(target_note.noesis_id))
    return links


def collect_relationship_links(
    vault: Vault,
    notes: list[Note],
    key: str,
    *,
    expected_type: str | None = None,
) -> set[str]:
    links: set[str] = set()
    for note in notes:
        for item in as_list(note.metadata.get(key)):
            if not isinstance(item, str):
                continue
            for target in extract_wikilinks(item):
                target_note = vault.find_note(target)
                if target_note is None:
                    continue
                if expected_type is not None and target_note.type != expected_type:
                    continue
                links.add(wikilink(target_note.noesis_id))
    return links


def add_relationship_link(metadata: dict[str, Any], key: str, link: str) -> None:
    values = [str(value) for value in as_list(metadata.get(key))]
    if link not in values:
        values.append(link)
    metadata[key] = values


def remove_relationship_link(
    vault: Vault,
    metadata: dict[str, Any],
    key: str,
    target_noesis_id: str,
) -> None:
    kept: list[Any] = []
    for item in as_list(metadata.get(key)):
        if not isinstance(item, str):
            kept.append(item)
            continue
        remove_item = False
        for target in extract_wikilinks(item):
            target_note = vault.find_note(target)
            if target_note is not None and target_note.noesis_id == target_noesis_id:
                remove_item = True
                break
        if not remove_item:
            kept.append(item)
    metadata[key] = kept


def relationship_contains(
    vault: Vault,
    metadata: dict[str, Any],
    key: str,
    target_noesis_id: str,
) -> bool:
    for item in as_list(metadata.get(key)):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            target_note = vault.find_note(target)
            if target_note is not None and target_note.noesis_id == target_noesis_id:
                return True
    return False


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
