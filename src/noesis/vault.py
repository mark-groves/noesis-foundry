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

from .version import __version__
from .storage import atomic_write_text, vault_lock, vault_write_operation


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
CONTRACT_VERSION = "2"
LEGACY_CONTRACT_VERSIONS = {"1"}
CONTRACT_KIND = "vault"
CONTRACT_SOURCE_OF_TRUTH = "markdown-flat-yaml"
NOESIS_VERSION = __version__
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
    "freshness_excluded",
}

RELATIONSHIP_TARGET_TYPES: dict[str, set[str]] = {
    "sources": {"source"},
    "evidence": {"evidence"},
    "claims": {"claim"},
    "syntheses": {"synthesis"},
    "reviewed_knowledge": {"reviewed-knowledge"},
    "reviewed_by": {"review"},
    "freshness_excluded": {"reviewed-knowledge"},
}

REQUIRED_RELATIONSHIPS: dict[str, set[str]] = {
    "evidence": {"sources"},
    "claim": {"sources", "evidence"},
    "synthesis": {"sources", "evidence", "claims"},
    "reviewed-knowledge": {"sources", "evidence", "claims", "syntheses", "reviewed_by"},
}

MATURE_REVIEW_STATES = {"approved", "reviewed"}
PLACEHOLDER_MARKERS = (
    "replace this placeholder",
    "<slug>",
    "<source-id>",
    "<evidence-id>",
    "<claim-id>",
    "<synthesis-id>",
    "{{title}}",
    "{{date}}",
)

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
    score: float
    content_chars: int
    freshness_state: str = "not-applicable"
    review_due_on: str | None = None
    valid_until: str | None = None


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
    "coding": ContextProfile(
        name="coding",
        description="Prefer architecture, commands, traps, decisions, and handoff guidance for software work.",
        default_limit=6,
        default_max_chars=14000,
    ),
    "agent-handoff": ContextProfile(
        name="agent-handoff",
        description="Render a harness-agnostic handoff pack for launching parallel agent work.",
        default_limit=6,
        default_max_chars=14000,
    ),
    "project-continuation": ContextProfile(
        name="project-continuation",
        description="Prefer a broad, current briefing for continuing implementation work.",
        default_limit=8,
        default_max_chars=16000,
    ),
    "codex-handoff": ContextProfile(
        name="codex-handoff",
        description="Render a Codex-ready adapter of the generic agent handoff pack.",
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
    "study": ContextProfile(
        name="study",
        description="Prefer objectives, weak areas, prior mistakes, resources, and scheduled review guidance.",
        default_limit=8,
        default_max_chars=18000,
    ),
}
CONTEXT_PROFILE_NAMES = set(CONTEXT_PROFILES)
FRESHNESS_POLICIES = {"balanced", "strict"}


@dataclass(frozen=True)
class ContextPackage:
    profile: str | None
    profile_description: str | None
    scope: str | None
    purpose: str | None
    as_of: str
    freshness_policy: str
    input_hashes: tuple[str, ...]
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
    freshness_excluded: list[ContextSelection]
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


@dataclass(frozen=True)
class VaultMigration:
    root: Path
    from_version: str
    to_version: str
    dry_run: bool
    changed_paths: list[Path]
    backup_path: Path | None


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
        return validate_vault(self)

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
                    or relationship_contains(self, note.metadata, "freshness_excluded", target.noesis_id)
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

    return validate_contract_metadata(path, metadata)


def validate_contract_metadata(path: Path, value: Any) -> list[Issue]:
    if not isinstance(value, dict):
        return [Issue(path, "Noesis contract metadata must be a YAML mapping")]
    metadata = value

    issues: list[Issue] = []
    for key, value in metadata.items():
        if isinstance(value, dict):
            issues.append(Issue(path, f"Noesis contract property {key!r} must be flat, not a mapping"))

    missing = sorted(CONTRACT_REQUIRED_PROPERTIES - metadata.keys())
    if missing:
        issues.append(Issue(path, f"missing Noesis contract properties: {', '.join(missing)}"))

    if metadata.get("noesis_contract") != CONTRACT_KIND:
        issues.append(Issue(path, f"noesis_contract must be {CONTRACT_KIND!r}"))
    contract_version = str(metadata.get("contract_version", ""))
    if contract_version != CONTRACT_VERSION:
        if contract_version in LEGACY_CONTRACT_VERSIONS:
            issues.append(
                Issue(
                    path,
                    f"contract_version {contract_version!r} requires migration to {CONTRACT_VERSION!r}; "
                    "run noesis vault migrate <path>",
                )
            )
        else:
            issues.append(Issue(path, f"contract_version must be supported version {CONTRACT_VERSION!r}"))
    if metadata.get("source_of_truth") != CONTRACT_SOURCE_OF_TRUTH:
        issues.append(Issue(path, f"source_of_truth must be {CONTRACT_SOURCE_OF_TRUTH!r}"))
    if "requires_noesis" in metadata:
        issues.extend(validate_requires_noesis(path, metadata["requires_noesis"]))
    for date_key in ("created", "updated"):
        if date_key in metadata and not is_date_like(metadata[date_key]):
            issues.append(Issue(path, f"{date_key} must be a date or date-like string"))

    return issues


def validate_vault(
    vault: Vault,
    *,
    contract_metadata: dict[str, Any] | None = None,
) -> list[Issue]:
    issues = list(vault.issues)
    if contract_metadata is None:
        issues.extend(validate_contract(vault.root))
    else:
        issues.extend(validate_contract_metadata(vault.root / CONTRACT_FILE, contract_metadata))
    issues.extend(validate_folders(vault.root))
    issues.extend(validate_notes(vault))
    issues.extend(validate_wikilinks(vault))
    issues.extend(validate_bases(vault.root))
    issues.extend(validate_canvases(vault.root))
    return sorted(issues, key=lambda issue: issue.path.as_posix())


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

        for date_key in (
            "created",
            "updated",
            "source_date",
            "captured",
            "reviewed_at",
            "next_review",
            "valid_until",
            "as_of",
        ):
            if date_key in metadata and not is_date_like(metadata[date_key]):
                issues.append(Issue(note.path, f"{date_key} must be a date or date-like string"))

        issues.extend(validate_type_stage(note))
        issues.extend(validate_relationship_syntax(note))
        issues.extend(validate_relationship_types(vault, note))
        issues.extend(validate_note_contract(vault, note))
        issues.extend(validate_source_integrity(vault, note))
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


def validate_relationship_types(vault: Vault, note: Note) -> list[Issue]:
    issues: list[Issue] = []
    for key, expected_types in RELATIONSHIP_TARGET_TYPES.items():
        for item in as_list(note.metadata.get(key)):
            if not isinstance(item, str):
                continue
            for target in extract_wikilinks(item):
                target_note = vault.find_note(target)
                if target_note is None:
                    continue
                if target_note.type not in expected_types:
                    expected = ", ".join(sorted(expected_types))
                    issues.append(
                        Issue(
                            note.path,
                            f"{key} relationship [[{target}]] must reference note type {expected}; "
                            f"found {target_note.type!r}",
                        )
                    )
    return issues


def validate_note_contract(vault: Vault, note: Note) -> list[Issue]:
    issues: list[Issue] = []
    for key in sorted(REQUIRED_RELATIONSHIPS.get(note.type, set())):
        if not relationship_notes(vault, note, key):
            issues.append(Issue(note.path, f"{note.type} requires at least one valid {key} relationship"))

    mature = note.review_state in MATURE_REVIEW_STATES or note.status in {"active", "reviewed"}
    if mature:
        lowered_body = note.body.casefold()
        for marker in PLACEHOLDER_MARKERS:
            if marker.casefold() in lowered_body:
                issues.append(Issue(note.path, f"mature note contains unresolved placeholder {marker!r}"))

    if note.type == "review":
        reviewer_value = note.metadata.get("reviewer")
        reviewer = reviewer_value.strip().casefold() if isinstance(reviewer_value, str) else ""
        if not isinstance(reviewer_value, str) or reviewer in {"", "unknown", "unassigned"}:
            issues.append(Issue(note.path, "review audit requires an identified reviewer"))
        if not relationship_notes(vault, note, "reviewed_notes"):
            issues.append(Issue(note.path, "review audit requires at least one reviewed_notes relationship"))
        decision_value = note.metadata.get("decision")
        decision = "" if is_blank(decision_value) else str(decision_value).strip()
        if not decision:
            issues.append(Issue(note.path, "review audit requires a decision"))
        elif decision not in {"approved", "changes-requested", "renewed"}:
            issues.append(Issue(note.path, "review decision must be approved, changes-requested, or renewed"))
        if decision in {"approved", "changes-requested", "renewed"}:
            if not has_completed_review_state(note):
                issues.append(
                    Issue(
                        note.path,
                        "review decision audit must have complete status and a mature review_state",
                    )
                )
            if parse_review_date(note.metadata.get("reviewed_at")) is None:
                issues.append(Issue(note.path, "review decision audit requires a parseable reviewed_at date"))
        if not markdown_body_section(note.body, "Basis"):
            issues.append(Issue(note.path, "review audit requires a non-empty Basis section"))
        if decision == "renewed" and parse_review_date(note.metadata.get("next_review")) is None:
            issues.append(Issue(note.path, "renewed review audit requires next_review"))
        if decision == "changes-requested" and not markdown_body_section(note.body, "Changes Requested"):
            issues.append(Issue(note.path, "changes-requested review audit requires requested-change details"))

    if (
        note.type == "reviewed-knowledge"
        and note.status in CURRENT_KNOWLEDGE_STATUSES
        and not is_excluded(note)
    ):
        issues.extend(validate_mature_knowledge_lineage(vault, note))
    return issues


def validate_mature_knowledge_lineage(vault: Vault, note: Note) -> list[Issue]:
    issues: list[Issue] = []
    auditable_lineage_ids = {note.noesis_id}
    lineage_sources = {
        source.noesis_id: source
        for source in relationship_notes(vault, note, "sources", expected_type="source")
    }

    for key, expected_type in (("evidence", "evidence"), ("claims", "claim"), ("syntheses", "synthesis")):
        for support in relationship_notes(vault, note, key, expected_type=expected_type):
            auditable_lineage_ids.add(support.noesis_id)
            for source in relationship_notes(vault, support, "sources", expected_type="source"):
                lineage_sources[source.noesis_id] = source
            if (
                support.status != "reviewed"
                or support.review_state not in MATURE_REVIEW_STATES
                or is_excluded(support)
            ):
                issues.append(
                    Issue(
                        note.path,
                        f"active reviewed knowledge depends on non-current {expected_type} {support.noesis_id!r}",
                    )
                )
            elif not approved_review_audits_for(vault, support):
                issues.append(
                    Issue(
                        note.path,
                        f"active reviewed knowledge depends on unaudited {expected_type} {support.noesis_id!r}",
                    )
                )

    for source in sorted(lineage_sources.values(), key=lambda item: item.rel_path.as_posix()):
        if is_excluded(source):
            issues.append(
                Issue(
                    note.path,
                    f"active reviewed knowledge depends on non-current source {source.noesis_id!r}",
                )
            )

    approved_audits = [
        audit
        for audit in relationship_notes(vault, note, "reviewed_by", expected_type="review")
        if is_completed_review_audit(audit)
        and str(audit.metadata.get("decision", "")) in {"approved", "renewed"}
        and any(
            relationship_contains(vault, audit.metadata, "reviewed_notes", lineage_id)
            for lineage_id in auditable_lineage_ids
        )
    ]
    if not approved_audits:
        issues.append(
            Issue(
                note.path,
                "active reviewed knowledge requires an approved review audit covering it or its declared lineage",
            )
        )
    return issues


def validate_source_integrity(vault: Vault, note: Note) -> list[Issue]:
    if note.type != "source":
        return []
    issues: list[Issue] = []
    raw_path = note.metadata.get("raw_path")
    if not isinstance(raw_path, str) or is_blank(raw_path):
        return [Issue(note.path, "source requires raw_path")]
    candidate = (note.path.parent / raw_path).resolve()
    try:
        candidate.relative_to(vault.root)
    except ValueError:
        return [Issue(note.path, "raw_path must remain inside the vault")]
    if not candidate.is_file():
        return [Issue(note.path, f"raw_path target is missing: {raw_path}")]

    expected_hash = note.metadata.get("content_hash")
    if not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        issues.append(Issue(note.path, "source requires a sha256 content_hash"))
    else:
        actual_hash = file_content_hash(candidate)
        if actual_hash != expected_hash:
            issues.append(Issue(note.path, f"raw source content hash mismatch: expected {expected_hash}, found {actual_hash}"))
    if note.metadata.get("content_hash_algorithm") != "sha256":
        issues.append(Issue(note.path, "source content_hash_algorithm must be 'sha256'"))
    expected_size = note.metadata.get("source_size_bytes")
    if not isinstance(expected_size, int):
        issues.append(Issue(note.path, "source requires integer source_size_bytes"))
    elif candidate.stat().st_size != expected_size:
        issues.append(
            Issue(
                note.path,
                f"raw source size mismatch: expected {expected_size}, found {candidate.stat().st_size}",
            )
        )
    return issues


def validate_context_exclusions(vault: Vault, note: Note) -> list[Issue]:
    issues: list[Issue] = []
    if note.type != "operational-context":
        return issues

    as_of_value = note.metadata.get("as_of")
    if is_blank(as_of_value):
        issues.append(Issue(note.path, "operational context requires as_of"))
        try:
            as_of = context_as_of_date(note.metadata.get("created"))
        except ValueError:
            as_of = date.today()
    else:
        try:
            as_of = context_as_of_date(as_of_value)
        except ValueError as exc:
            issues.append(Issue(note.path, str(exc)))
            as_of = date.today()

    freshness_policy_value = note.metadata.get("freshness_policy")
    if is_blank(freshness_policy_value):
        issues.append(Issue(note.path, "operational context requires freshness_policy"))
        freshness_policy = "balanced"
    else:
        try:
            freshness_policy = resolve_freshness_policy(str(freshness_policy_value))
        except ValueError as exc:
            issues.append(Issue(note.path, str(exc)))
            freshness_policy = "balanced"

    input_hash_digests: dict[str, str] | None = None
    if "input_hashes" not in note.metadata:
        issues.append(Issue(note.path, "operational context requires input_hashes"))
    else:
        input_hashes = note.metadata["input_hashes"]
        if not isinstance(input_hashes, list):
            issues.append(Issue(note.path, "input_hashes must be a list of noesis_id=sha256:<digest> strings"))
        else:
            parsed_input_hashes: list[tuple[str, str]] = []
            for item in input_hashes:
                match = re.fullmatch(r"([^=]+)=sha256:([0-9a-f]{64})", str(item))
                if match is None:
                    issues.append(
                        Issue(note.path, "input_hashes must be a list of noesis_id=sha256:<digest> strings")
                    )
                    continue
                parsed_input_hashes.append((match.group(1), f"sha256:{match.group(2)}"))
            parsed_input_hash_ids = [note_id for note_id, _ in parsed_input_hashes]
            if len(parsed_input_hash_ids) != len(set(parsed_input_hash_ids)):
                issues.append(Issue(note.path, "input_hashes must not contain duplicate noesis_id entries"))
            input_hash_digests = dict(parsed_input_hashes)

    reviewed_knowledge_ids: set[str] = set()
    reviewed_knowledge_hashes: dict[str, str] = {}
    for ref in as_list(note.metadata.get("reviewed_knowledge")):
        if not isinstance(ref, str):
            continue
        for target_ref in extract_wikilinks(ref):
            target = vault.find_note(target_ref)
            if target is None:
                continue
            reviewed_knowledge_ids.add(target.noesis_id)
            reviewed_knowledge_hashes[target.noesis_id] = file_content_hash(target.path)
            if target.type != "reviewed-knowledge" or target.review_state not in {"reviewed", "approved"}:
                issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is not reviewed knowledge"))
            elif target.status not in CURRENT_KNOWLEDGE_STATUSES:
                issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is not current reviewed knowledge"))
            elif is_excluded(target):
                issues.append(Issue(note.path, f"reviewed_knowledge reference {ref!r} is stale, superseded, or archived"))
            else:
                freshness_state, _, _ = note_freshness(target, as_of=as_of)
                if not context_freshness_eligible(freshness_state, policy=freshness_policy):
                    issues.append(
                        Issue(
                            note.path,
                            f"reviewed_knowledge reference {ref!r} is {freshness_state} as of {as_of.isoformat()} "
                            f"under {freshness_policy!r} freshness policy",
                        )
                    )

    freshness_excluded_ids = {
        target.noesis_id
        for target in context_linked_notes(vault, note.metadata, "freshness_excluded")
    }
    overlap = sorted(reviewed_knowledge_ids & freshness_excluded_ids)
    if overlap:
        issues.append(
            Issue(
                note.path,
                "reviewed_knowledge and freshness_excluded must not overlap: " + ", ".join(overlap),
            )
        )

    if input_hash_digests is not None and set(input_hash_digests) != reviewed_knowledge_ids:
        missing = sorted(reviewed_knowledge_ids - set(input_hash_digests))
        extra = sorted(set(input_hash_digests) - reviewed_knowledge_ids)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(extra)}")
        issues.append(Issue(note.path, f"input_hashes must match reviewed_knowledge references ({'; '.join(details)})"))

    for note_id in sorted(reviewed_knowledge_ids & set(input_hash_digests or {})):
        recorded_hash = input_hash_digests[note_id]
        actual_hash = reviewed_knowledge_hashes[note_id]
        if recorded_hash != actual_hash:
            issues.append(
                Issue(
                    note.path,
                    f"input_hashes digest for reviewed knowledge {note_id!r} does not match its file content",
                )
            )

    for ref in as_list(note.metadata.get("excluded_memory")):
        if not isinstance(ref, str):
            continue
        for target_ref in extract_wikilinks(ref):
            target = vault.find_note(target_ref)
            if target is not None and not is_context_excluded(target):
                issues.append(
                    Issue(
                        note.path,
                        f"excluded_memory reference {ref!r} is not stale, superseded, archived, "
                        "or changes-requested",
                    )
                )

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


def migrate_vault(
    path: Path | str,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> VaultMigration:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"vault path is not a directory: {root}")
    if dry_run:
        return _migrate_vault_locked(root, dry_run=True, backup=backup)
    with vault_lock(root):
        return _migrate_vault_locked(root, dry_run=dry_run, backup=backup)


def _migrate_vault_locked(
    path: Path | str,
    *,
    dry_run: bool = False,
    backup: bool = True,
) -> VaultMigration:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"vault path is not a directory: {root}")
    contract_path = root / CONTRACT_FILE
    contract = read_contract(root)
    from_version = str(contract.get("contract_version", ""))
    if from_version == CONTRACT_VERSION:
        return VaultMigration(root, from_version, CONTRACT_VERSION, dry_run, [], None)
    if from_version not in LEGACY_CONTRACT_VERSIONS:
        raise ValueError(
            f"cannot migrate contract_version {from_version!r}; supported legacy versions: "
            f"{', '.join(sorted(LEGACY_CONTRACT_VERSIONS))}"
        )

    vault = Vault.load(root)
    if vault.issues:
        formatted = "; ".join(issue.format(root) for issue in vault.issues[:3])
        raise ValueError(f"cannot migrate unreadable vault: {formatted}")

    note_updates: dict[Path, tuple[dict[str, Any], str]] = {}
    for note in vault.notes:
        metadata = dict(note.metadata)
        if note.type == "source":
            raw_path = metadata.get("raw_path")
            if isinstance(raw_path, str) and not is_blank(raw_path):
                raw_target = (note.path.parent / raw_path).resolve()
                try:
                    raw_target.relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"cannot migrate source with external raw_path: {note.rel_path}") from exc
                if not raw_target.is_file():
                    raise ValueError(f"cannot migrate source with missing raw file: {note.rel_path}")
                metadata["content_hash"] = file_content_hash(raw_target)
                metadata["content_hash_algorithm"] = "sha256"
                metadata["source_size_bytes"] = raw_target.stat().st_size
        if note.noesis_id == "review-queue" and note.type == "review" and metadata.get("decision") is None:
            metadata["type"] = "dashboard"
            metadata.pop("reviewer", None)
        if note.type == "operational-context":
            try:
                if is_blank(metadata.get("as_of")):
                    raise ValueError("missing as_of")
                context_as_of_date(metadata.get("as_of"))
            except ValueError:
                try:
                    migrated_as_of = context_as_of_date(metadata.get("created"))
                except ValueError:
                    migrated_as_of = date.today()
                metadata["as_of"] = migrated_as_of.isoformat()
            metadata.setdefault("freshness_policy", "balanced")
            metadata.setdefault("freshness_excluded", [])
            context_inputs = context_reviewed_knowledge(vault, metadata)
            metadata["input_hashes"] = [
                f"{context_input.noesis_id}={file_content_hash(context_input.path)}"
                for context_input in context_inputs
            ]
        if metadata != note.metadata:
            note_updates[note.path] = (metadata, note.body)

    for knowledge in vault.notes:
        if knowledge.type != "reviewed-knowledge" or knowledge.status not in CURRENT_KNOWLEDGE_STATUSES:
            continue
        sources = relationship_notes(vault, knowledge, "sources", expected_type="source")
        if not sources:
            raise ValueError(f"cannot migrate active knowledge without sources: {knowledge.noesis_id}")
        for source in sources:
            if is_excluded(source):
                raise ValueError(
                    f"cannot migrate active knowledge with excluded source: {source.noesis_id}"
                )

        auditable_lineage_ids = {knowledge.noesis_id}
        supports_by_key: dict[str, list[Note]] = {}
        for key, expected_type in (("evidence", "evidence"), ("claims", "claim"), ("syntheses", "synthesis")):
            supports = relationship_notes(vault, knowledge, key, expected_type=expected_type)
            if not supports:
                raise ValueError(f"cannot migrate active knowledge without {key}: {knowledge.noesis_id}")
            for support in supports:
                if (
                    is_excluded(support)
                    or support.status != "reviewed"
                    or support.review_state not in MATURE_REVIEW_STATES
                ):
                    raise ValueError(
                        f"cannot migrate active knowledge with excluded, blocked, or unreviewed {expected_type}: "
                        f"{support.noesis_id}"
                    )
                for source in relationship_notes(vault, support, "sources", expected_type="source"):
                    if is_excluded(source):
                        raise ValueError(
                            "cannot migrate active knowledge with excluded support source: "
                            f"{source.noesis_id}"
                        )
                auditable_lineage_ids.add(support.noesis_id)
            supports_by_key[key] = supports

        audits = relationship_notes(vault, knowledge, "reviewed_by", expected_type="review")
        approved_audits = [
            audit
            for audit in audits
            if is_completed_review_audit(audit)
            and str(audit.metadata.get("decision", "")) in {"approved", "renewed"}
            and any(
                relationship_contains(vault, audit.metadata, "reviewed_notes", lineage_id)
                for lineage_id in auditable_lineage_ids
            )
        ]
        if not approved_audits:
            raise ValueError(
                "cannot migrate active knowledge without an approved audit covering it or its declared lineage: "
                f"{knowledge.noesis_id}"
            )
        audit = approved_audits[-1]
        audit_metadata = dict(note_updates.get(audit.path, (audit.metadata, audit.body))[0])
        for supports in supports_by_key.values():
            for support in supports:
                support_metadata = dict(note_updates.get(support.path, (support.metadata, support.body))[0])
                add_relationship_link(support_metadata, "reviewed_by", wikilink(audit.noesis_id))
                note_updates[support.path] = (support_metadata, support.body)
                add_relationship_link(audit_metadata, "reviewed_notes", wikilink(support.noesis_id))
        note_updates[audit.path] = (audit_metadata, audit.body)

    today = date.today().isoformat()
    migrated_contract = dict(contract)
    migrated_contract["contract_version"] = CONTRACT_VERSION
    migrated_contract["requires_noesis"] = f">={NOESIS_VERSION}"
    migrated_contract["updated"] = today

    projected_vault = project_vault_notes(vault, note_updates)
    projected_issues = validate_vault(projected_vault, contract_metadata=migrated_contract)
    if projected_issues:
        formatted = "; ".join(issue.format(root) for issue in projected_issues[:3])
        remaining = len(projected_issues) - 3
        if remaining > 0:
            formatted += f"; and {remaining} more issue(s)"
        raise ValueError(f"cannot migrate invalid projected vault: {formatted}")

    changed_paths = sorted([*note_updates, contract_path], key=lambda item: item.as_posix())
    if dry_run:
        return VaultMigration(root, from_version, CONTRACT_VERSION, True, changed_paths, None)

    backup_path: Path | None = None
    if backup:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = root.parent / f"{root.name}.backup-v{from_version}-{timestamp}"
        suffix = 2
        while backup_path.exists():
            backup_path = root.parent / f"{root.name}.backup-v{from_version}-{timestamp}-{suffix}"
            suffix += 1
        shutil.copytree(root, backup_path)

    original_text = {target: target.read_text(encoding="utf-8") for target in changed_paths}
    try:
        with vault_lock(root):
            for target, (metadata, body) in note_updates.items():
                write_note(target, metadata, body)
            atomic_write_text(
                contract_path,
                yaml.safe_dump(migrated_contract, sort_keys=False, allow_unicode=False),
            )
            migrated = Vault.load(root)
            issues = migrated.validate()
            if issues:
                formatted = "; ".join(issue.format(root) for issue in issues[:5])
                raise ValueError(f"migration produced invalid vault: {formatted}")
    except Exception:
        for target, content in original_text.items():
            atomic_write_text(target, content)
        raise
    return VaultMigration(root, from_version, CONTRACT_VERSION, False, changed_paths, backup_path)


def project_vault_notes(
    vault: Vault,
    note_updates: dict[Path, tuple[dict[str, Any], str]],
) -> Vault:
    projected = Vault(
        root=vault.root,
        issues=list(vault.issues),
        by_link=dict(vault.by_link),
    )
    for note in vault.notes:
        metadata, body = note_updates.get(note.path, (note.metadata, note.body))
        projected_note = Note(
            path=note.path,
            rel_path=note.rel_path,
            metadata=metadata,
            body=body,
        )
        projected.notes.append(projected_note)
        projected.register_note_aliases(projected_note)
        if projected_note.noesis_id:
            if projected_note.noesis_id in projected.by_id:
                projected.issues.append(
                    Issue(projected_note.path, f"duplicate noesis_id {projected_note.noesis_id!r}")
                )
            projected.by_id[projected_note.noesis_id] = projected_note
            projected.by_link[projected_note.noesis_id] = projected_note.path
    return projected


@vault_write_operation(create_root=True)
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
        atomic_write_text(target, content)
        created.append(target)

    return created


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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


@vault_write_operation
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
    if is_blank(reviewer) or str(reviewer).strip().casefold() in {"unknown", "unassigned"}:
        raise ValueError("reviewer must identify the human or agent performing the review")
    if is_blank(basis):
        raise ValueError("basis is required for a scheduled review")
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

    basis_text = str(basis).strip()
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
    writes = [(target.path, target_metadata, target.body), (note_path, review_metadata, body)]
    append_updated_reviewed_knowledge_contexts(
        vault,
        target,
        target_metadata,
        target.body,
        renewed_at,
        writes,
    )
    write_notes_and_validate(root, writes)
    return CreatedNote(note_id=note_id, path=note_path)


@vault_write_operation
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
    if is_blank(reviewer) or str(reviewer).strip().casefold() in {"unknown", "unassigned"}:
        raise ValueError("reviewer must identify the human or agent performing the review")
    if is_blank(basis):
        raise ValueError("basis is required for a review decision")
    if decision == "changes-requested" and is_blank(changes_requested):
        raise ValueError("changes_requested is required when requesting changes")
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

    basis_text = str(basis).strip()
    requested_changes_text = "None." if decision == "approved" else str(changes_requested).strip()
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
    else:
        append_updated_reviewed_knowledge_contexts(
            vault,
            target,
            target_metadata,
            target.body,
            reviewed_at,
            writes,
        )
    write_notes_and_validate(root, writes)
    return CreatedNote(note_id=note_id, path=note_path)


@vault_write_operation
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


@vault_write_operation
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

    pending_lifecycle_excluded: list[Note] = []
    for pending_path, pending_metadata, pending_body in writes:
        pending_note = Note(
            path=pending_path,
            rel_path=pending_path.relative_to(root),
            metadata=pending_metadata,
            body=pending_body,
        )
        if is_excluded(pending_note):
            pending_lifecycle_excluded.append(pending_note)

    stale_link = wikilink(note_id)
    for context_note in vault.notes:
        if context_note.type != "operational-context":
            continue
        if not context_references_memory(vault, context_note, target.noesis_id):
            continue
        context_metadata = dict(context_note.metadata)
        remaining_knowledge = remaining_context_knowledge(vault, context_metadata, target.noesis_id)
        context_metadata["reviewed_knowledge"] = [wikilink(note.noesis_id) for note in remaining_knowledge]
        if "input_hashes" in context_metadata:
            context_metadata["input_hashes"] = [
                f"{note.noesis_id}={file_content_hash(note.path)}" for note in remaining_knowledge
            ]
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
            as_of=context_metadata.get("as_of", context_metadata.get("created")),
            freshness_policy=str(context_metadata.get("freshness_policy", "balanced")),
            profile=context_profile(context_note),
            limit=context_budget(context_note, "context_limit"),
            max_chars=context_budget(context_note, "context_max_chars"),
            freshness_excluded_notes=context_linked_notes(vault, context_metadata, "freshness_excluded"),
            lifecycle_excluded_notes=pending_lifecycle_excluded,
        )
        writes.append((context_note.path, context_metadata, context_body))

    write_notes_and_validate(root, writes)
    return CreatedNote(note_id=note_id, path=note_path)


@vault_write_operation
def write_context_note(
    vault_path: Path | str,
    *,
    scope: str | None = None,
    purpose: str | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
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
        as_of=as_of,
        freshness_policy=freshness_policy,
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
    freshness_excluded_links = [wikilink(selection.note.noesis_id) for selection in package.freshness_excluded]
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
        "freshness_excluded": freshness_excluded_links,
        "as_of": package.as_of,
        "freshness_policy": package.freshness_policy,
        "input_hashes": list(package.input_hashes),
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
    from .scaffold import default_vault_files as implementation

    return implementation(today)


def template_files(today: str) -> dict[Path, str]:
    from .scaffold import template_files as implementation

    return implementation(today)



def build_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
) -> str:
    from .context import build_context as implementation

    return implementation(
        vault,
        scope=scope,
        purpose=purpose,
        limit=limit,
        max_chars=max_chars,
        profile=profile,
        as_of=as_of,
        freshness_policy=freshness_policy,
    )


def compose_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
) -> ContextPackage:
    from .context import compose_context as implementation

    return implementation(
        vault,
        scope=scope,
        purpose=purpose,
        limit=limit,
        max_chars=max_chars,
        profile=profile,
        as_of=as_of,
        freshness_policy=freshness_policy,
    )


def validate_context_budget(*, limit: int | None = None, max_chars: int | None = None) -> None:
    from .context import validate_context_budget as implementation

    implementation(limit=limit, max_chars=max_chars)


def context_as_of_date(value: str | date | None) -> date:
    from .context import context_as_of_date as implementation

    return implementation(value)


def resolve_freshness_policy(value: str | None) -> str:
    from .context import resolve_freshness_policy as implementation

    return implementation(value)


def note_freshness(note: Note, *, as_of: date) -> tuple[str, date | None, date | None]:
    from .context import note_freshness as implementation

    return implementation(note, as_of=as_of)


def context_freshness_eligible(state: str, *, policy: str) -> bool:
    from .context import context_freshness_eligible as implementation

    return implementation(state, policy=policy)


def context_lifecycle_exclusion_kind(note: Note) -> str:
    from .context import context_lifecycle_exclusion_kind as implementation

    return implementation(note)


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
    as_of: date | None = None,
    freshness_policy: str = "balanced",
    freshness_excluded: list[ContextSelection] | None = None,
) -> str:
    from .context import render_context as implementation

    return implementation(
        knowledge,
        scope=scope,
        purpose=purpose,
        profile=profile,
        limit=limit,
        max_chars=max_chars,
        total_candidates=total_candidates,
        excluded=excluded,
        as_of=as_of,
        freshness_policy=freshness_policy,
        freshness_excluded=freshness_excluded,
    )



def build_context_body(
    vault: Vault,
    knowledge: list[Note],
    excluded_links: list[str],
    *,
    scope: str | None = None,
    purpose: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
    profile: str | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    freshness_excluded_notes: list[Note] | None = None,
    lifecycle_excluded_notes: list[Note] | None = None,
    pending_notes: list[Note] | None = None,
) -> str:
    from .context import render_context_snapshot

    reviewed_knowledge_links = [wikilink(note.noesis_id) for note in knowledge]
    synthesis_links = sorted(collect_relationship_links(vault, knowledge, "syntheses", expected_type="synthesis"))
    body = (
        render_context_snapshot(
            vault,
            knowledge,
            scope=scope,
            purpose=purpose,
            profile=profile,
            limit=limit,
            max_chars=max_chars,
            as_of=as_of,
            freshness_policy=freshness_policy,
            freshness_excluded_notes=freshness_excluded_notes,
            lifecycle_excluded_notes=lifecycle_excluded_notes,
            pending_notes=pending_notes,
        ).rstrip()
        + "\n\n## Traceability\n\n"
    )
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
        original_knowledge = context_reviewed_knowledge(vault, context_metadata)
        remaining_knowledge = remaining_context_knowledge(vault, context_metadata, target.noesis_id)
        remaining_knowledge_ids = {note.noesis_id for note in remaining_knowledge}
        removed_knowledge = [
            note
            for note in original_knowledge
            if note.noesis_id not in remaining_knowledge_ids
        ]
        context_metadata["reviewed_knowledge"] = [wikilink(note.noesis_id) for note in remaining_knowledge]
        if "input_hashes" in context_metadata:
            context_metadata["input_hashes"] = [
                f"{note.noesis_id}={file_content_hash(note.path)}" for note in remaining_knowledge
            ]
        context_metadata["syntheses"] = sorted(
            collect_relationship_links(vault, remaining_knowledge, "syntheses", expected_type="synthesis")
        )
        remove_relationship_link(vault, context_metadata, "syntheses", target.noesis_id)
        add_relationship_link(context_metadata, "excluded_memory", wikilink(target.noesis_id))
        for removed_note in removed_knowledge:
            add_relationship_link(context_metadata, "excluded_memory", wikilink(removed_note.noesis_id))
        context_metadata["updated"] = reviewed_at
        context_body = build_context_body(
            vault,
            remaining_knowledge,
            sorted(str(link) for link in as_list(context_metadata.get("excluded_memory"))),
            scope=context_scope(context_note),
            purpose=context_purpose(context_note),
            as_of=context_metadata.get("as_of", context_metadata.get("created")),
            freshness_policy=str(context_metadata.get("freshness_policy", "balanced")),
            profile=context_profile(context_note),
            limit=context_budget(context_note, "context_limit"),
            max_chars=context_budget(context_note, "context_max_chars"),
            freshness_excluded_notes=context_linked_notes(vault, context_metadata, "freshness_excluded"),
        )
        writes.append((context_note.path, context_metadata, context_body))


def append_updated_reviewed_knowledge_contexts(
    vault: Vault,
    target: Note,
    target_metadata: dict[str, Any],
    target_body: str,
    updated_at: str,
    writes: list[tuple[Path, dict[str, Any], str]],
) -> None:
    projected_target = Note(
        path=target.path,
        rel_path=target.rel_path,
        metadata=target_metadata,
        body=target_body,
    )
    if (
        projected_target.status not in CURRENT_KNOWLEDGE_STATUSES
        or projected_target.review_state not in {"reviewed", "approved"}
        or is_excluded(projected_target)
    ):
        return

    projected_target_hash = note_content_hash(target_metadata, target_body)
    pending_notes = [
        Note(
            path=path,
            rel_path=path.relative_to(vault.root),
            metadata=metadata,
            body=body,
        )
        for path, metadata, body in writes
        if not is_blank(metadata.get("noesis_id"))
    ]
    for context_note in vault.notes:
        if context_note.type != "operational-context":
            continue
        included_target = relationship_contains(
            vault,
            context_note.metadata,
            "reviewed_knowledge",
            target.noesis_id,
        )
        review_excluded_target = relationship_contains(
            vault,
            context_note.metadata,
            "excluded_memory",
            target.noesis_id,
        )
        if not included_target and not review_excluded_target:
            continue
        context_metadata = dict(context_note.metadata)
        if review_excluded_target:
            remove_relationship_link(vault, context_metadata, "excluded_memory", target.noesis_id)
        knowledge = [
            projected_target if note.noesis_id == target.noesis_id else note
            for note in context_reviewed_knowledge(vault, context_metadata)
        ]
        if (
            projected_target.type == "reviewed-knowledge"
            and all(note.noesis_id != projected_target.noesis_id for note in knowledge)
        ):
            context_as_of = context_as_of_date(
                context_metadata.get("as_of", context_metadata.get("created"))
            )
            freshness_policy = resolve_freshness_policy(
                str(context_metadata.get("freshness_policy", "balanced"))
            )
            freshness_state, _, _ = note_freshness(projected_target, as_of=context_as_of)
            already_freshness_excluded = relationship_contains(
                vault,
                context_metadata,
                "freshness_excluded",
                target.noesis_id,
            )
            if context_freshness_eligible(freshness_state, policy=freshness_policy):
                if not already_freshness_excluded:
                    knowledge.append(projected_target)
            else:
                add_relationship_link(
                    context_metadata,
                    "freshness_excluded",
                    wikilink(projected_target.noesis_id),
                )
        context_metadata["reviewed_knowledge"] = [wikilink(note.noesis_id) for note in knowledge]
        context_metadata["input_hashes"] = [
            f"{note.noesis_id}="
            f"{projected_target_hash if note.noesis_id == target.noesis_id else file_content_hash(note.path)}"
            for note in knowledge
        ]
        context_metadata["syntheses"] = sorted(
            collect_relationship_links(vault, knowledge, "syntheses", expected_type="synthesis")
        )
        context_metadata["updated"] = updated_at
        freshness_excluded_notes = [
            projected_target if note.noesis_id == projected_target.noesis_id else note
            for note in context_linked_notes(vault, context_metadata, "freshness_excluded")
        ]
        context_body = build_context_body(
            vault,
            knowledge,
            sorted(str(link) for link in as_list(context_metadata.get("excluded_memory"))),
            scope=context_scope(context_note),
            purpose=context_purpose(context_note),
            as_of=context_metadata.get("as_of", context_metadata.get("created")),
            freshness_policy=str(context_metadata.get("freshness_policy", "balanced")),
            profile=context_profile(context_note),
            limit=context_budget(context_note, "context_limit"),
            max_chars=context_budget(context_note, "context_max_chars"),
            freshness_excluded_notes=freshness_excluded_notes,
            pending_notes=pending_notes,
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


def context_profile(context_note: Note) -> str | None:
    profile = context_note.metadata.get("context_profile")
    if isinstance(profile, str) and not is_blank(profile):
        return profile
    return context_body_field(context_note, "Profile")


def context_budget(context_note: Note, key: str) -> int | None:
    value = context_note.metadata.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def context_linked_notes(vault: Vault, metadata: dict[str, Any], key: str) -> list[Note]:
    notes: list[Note] = []
    seen: set[str] = set()
    for item in as_list(metadata.get(key)):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            note = vault.find_note(target)
            if note is None or note.noesis_id in seen:
                continue
            notes.append(note)
            seen.add(note.noesis_id)
    return notes


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
    if note.type == "reviewed-knowledge":
        for key, expected_type in (
            ("evidence", "evidence"),
            ("claims", "claim"),
            ("syntheses", "synthesis"),
        ):
            if any(
                note_references_memory(vault, support, target_noesis_id)
                for support in relationship_notes(vault, note, key, expected_type=expected_type)
            ):
                return True
    return False


def filter_knowledge_by_scope(knowledge: list[Note], scope: str | None) -> list[Note]:
    if scope is None or not scope.strip():
        return knowledge
    from .retrieval import rank_notes

    return [hit.note for hit in rank_notes(knowledge, scope)]


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


def is_context_excluded(note: Note) -> bool:
    return is_excluded(note) or note.review_state == "changes-requested"


def has_completed_review_state(note: Note) -> bool:
    return (
        note.type == "review"
        and note.status == "complete"
        and note.review_state in MATURE_REVIEW_STATES
    )


def is_completed_review_audit(note: Note) -> bool:
    return has_completed_review_state(note) and parse_review_date(note.metadata.get("reviewed_at")) is not None


def approved_review_audits_for(vault: Vault, target: Note) -> list[Note]:
    return [
        audit
        for audit in vault.review_audits_for(target)
        if is_completed_review_audit(audit)
        and str(audit.metadata.get("decision", "")) in {"approved", "renewed"}
        and relationship_contains(vault, audit.metadata, "reviewed_notes", target.noesis_id)
    ]


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


def render_note_text(metadata: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=False)
    return f"---\n{frontmatter}---\n\n{body.rstrip()}\n"


def note_content_hash(metadata: dict[str, Any], body: str) -> str:
    digest = hashlib.sha256(render_note_text(metadata, body).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def write_note(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_note_text(metadata, body))


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
                atomic_write_text(path, text)
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


def relationship_notes(
    vault: Vault,
    note: Note,
    key: str,
    *,
    expected_type: str | None = None,
) -> list[Note]:
    notes: dict[str, Note] = {}
    for item in as_list(note.metadata.get(key)):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            target_note = vault.find_note(target)
            if target_note is None:
                continue
            if expected_type is not None and target_note.type != expected_type:
                continue
            notes[target_note.noesis_id] = target_note
    return sorted(notes.values(), key=lambda item: item.rel_path.as_posix())


def markdown_body_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


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
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
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
