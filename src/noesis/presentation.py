"""Transport-neutral JSON presenters shared by the CLI and MCP adapters."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from typing import Any

from .vault import (
    Note,
    Vault,
    is_completed_review_audit,
    is_context_excluded,
    is_excluded,
    note_review_due,
    parse_review_date,
    review_cutoff_date,
    review_requires_audit,
)


JsonObject = dict[str, Any]


def note_summary(note: Note, vault_root: Path) -> JsonObject:
    """Return a portable note summary without leaking host absolute paths."""

    try:
        rel_path = note.path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = note.rel_path.as_posix()
    return {
        "noesis_id": note.noesis_id,
        "title": note.title,
        "path": rel_path,
        "type": note.type,
        "lifecycle_stage": note.lifecycle_stage,
        "status": note.status,
        "review_state": note.review_state,
        "confidence": json_safe(note.metadata.get("confidence")),
        "updated": json_safe(note.metadata.get("updated")),
        "next_review": json_safe(note.metadata.get("next_review")),
        "valid_until": json_safe(note.metadata.get("valid_until")),
    }


def review_note_summary(note: Note, vault: Vault, *, due_on: str | None = None) -> JsonObject:
    data = note_summary(note, vault.root)
    audits = vault.review_audits_for(note)
    completed_audits = [audit for audit in audits if is_completed_review_audit(audit)]
    history = review_change_request_history(vault, completed_audits)
    open_changes = open_review_changes(note, completed_audits, history)
    data["review_schedule"] = review_due_details(note, due_on=due_on)
    data["audit"] = {
        "count": len(audits),
        "requires_audit": review_requires_audit(note),
        "has_audit": bool(completed_audits),
        "latest_decision": (
            json_safe(completed_audits[-1].metadata.get("decision")) if completed_audits else None
        ),
    }
    data["requested_changes"] = {
        "open": bool(open_changes),
        "count": len(open_changes),
        "history_count": len(history),
    }
    data["impact"] = {
        "dependent_reviewed_knowledge": len(vault.dependent_reviewed_knowledge_for(note)),
        "dependent_contexts": len(vault.dependent_contexts_for(note)),
    }
    data["lifecycle_safety"] = review_lifecycle_safety(note)
    return data


def review_filters(
    *,
    review_state: str | None = None,
    note_type: str | None = None,
    lifecycle_stage: str | None = None,
    due: bool = False,
    due_on: str | None = None,
) -> JsonObject:
    return {
        "review_state": review_state,
        "type": note_type,
        "lifecycle_stage": lifecycle_stage,
        "due": due,
        "due_on": due_on,
    }


def review_summary_to_dict(vault: Vault, summary: dict[str, Any], *, due_on: str | None = None) -> JsonObject:
    return {
        "ok": True,
        "vault_path": str(vault.root),
        "pending_count": summary["pending_count"],
        "due_count": summary["due_count"],
        "overdue_count": summary["overdue_count"],
        "requested_changes_count": summary["requested_changes_count"],
        "audit_gap_count": summary["audit_gap_count"],
        "due_on": due_on,
        "review_state_counts": json_safe(summary["review_state_counts"]),
        "due_notes": [review_note_summary(note, vault, due_on=due_on) for note in summary["due_notes"]],
        "overdue_notes": [review_note_summary(note, vault, due_on=due_on) for note in summary["overdue_notes"]],
        "requested_changes_notes": [
            review_note_summary(note, vault, due_on=due_on) for note in summary["requested_changes_notes"]
        ],
        "audit_gap_notes": [review_note_summary(note, vault, due_on=due_on) for note in summary["audit_gap_notes"]],
        "next_review_notes": [
            review_note_summary(note, vault, due_on=due_on) for note in summary["next_review_notes"]
        ],
    }


def review_workbench_to_dict(
    vault: Vault,
    note: Note,
    *,
    note_ref: str,
    due_on: str | None = None,
) -> JsonObject:
    audits = vault.review_audits_for(note)
    completed_audits = [audit for audit in audits if is_completed_review_audit(audit)]
    support = vault.support_notes_for(note)
    lineage = vault.lineage(note.noesis_id)
    review_due = note_review_due(note, due_on=due_on)
    schedule = review_due_details(note, due_on=due_on)
    dependent_knowledge = vault.dependent_reviewed_knowledge_for(note)
    dependent_contexts = vault.dependent_contexts_for(note)
    history = review_change_request_history(vault, completed_audits)
    open_changes = open_review_changes(note, completed_audits, history)
    requires_audit = review_requires_audit(note)
    audit_status = {
        "requires_audit": requires_audit,
        "has_audit": bool(completed_audits),
        "ok": (not requires_audit) or bool(completed_audits),
    }
    return {
        "ok": True,
        "vault_path": str(vault.root),
        "note_ref": note_ref,
        "note": note_to_dict(note, vault.root),
        "review_due": review_due,
        "review_schedule": review_schedule_to_dict(
            vault,
            note,
            completed_audits,
            due_on=due_on,
            review_due=review_due,
        ),
        "triage": review_triage(
            note,
            schedule=schedule,
            audit_status=audit_status,
            changes_requested=open_changes,
            dependent_reviewed_knowledge=dependent_knowledge,
            dependent_contexts=dependent_contexts,
        ),
        "audit_status": audit_status,
        "audit_records": [review_audit_to_dict(audit, vault.root) for audit in audits],
        "support": {
            key: [note_summary(support_note, vault.root) for support_note in notes]
            for key, notes in support.items()
        },
        "changes_requested": open_changes,
        "changes_requested_history": history,
        "impact": {
            "dependent_reviewed_knowledge": [note_summary(item, vault.root) for item in dependent_knowledge],
            "dependent_contexts": [note_summary(item, vault.root) for item in dependent_contexts],
            "counts": {
                "dependent_reviewed_knowledge": len(dependent_knowledge),
                "dependent_contexts": len(dependent_contexts),
            },
        },
        "lifecycle_safety": review_lifecycle_safety(note),
        "lineage": [note_summary(item, vault.root) for item in lineage],
    }


def issue_to_dict(issue: Any, vault_root: Path) -> JsonObject:
    try:
        rel_path = issue.path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = str(issue.path)
    return {"path": rel_path, "message": issue.message}


def note_to_dict(note: Note, vault_root: Path) -> JsonObject:
    data = note_summary(note, vault_root)
    data["metadata"] = json_safe(redact_host_paths(note.metadata))
    data["body"] = note.body
    return data


def review_due_details(note: Note, *, due_on: str | None = None) -> JsonObject:
    cutoff = review_cutoff_date(due_on)
    next_review = parse_review_date(note.metadata.get("next_review"))
    due = next_review is not None and next_review <= cutoff
    overdue = next_review is not None and next_review < cutoff
    days_overdue = (cutoff - next_review).days if overdue and next_review is not None else 0
    status = "unscheduled" if next_review is None else "overdue" if overdue else "due" if due else "scheduled"
    return {
        "next_review": next_review.isoformat() if next_review else json_safe(note.metadata.get("next_review")),
        "due_on": cutoff.isoformat(),
        "due": due,
        "overdue": overdue,
        "days_overdue": days_overdue,
        "status": status,
    }


def review_lifecycle_safety(note: Note) -> JsonObject:
    context_excluded = is_context_excluded(note)
    excluded = is_excluded(note)
    stale_memory = note.type == "stale-memory"
    return {
        "excluded_from_active_context": context_excluded,
        "stale_or_superseded_memory": stale_memory and excluded,
        "renewal_preserves_lifecycle": stale_memory and excluded,
    }


def review_change_request_history(vault: Vault, audits: list[Note]) -> list[JsonObject]:
    return [
        {
            "review": note_summary(audit, vault.root),
            "changes_requested": markdown_section(audit.body, "Changes Requested"),
        }
        for audit in audits
        if audit.metadata.get("decision") == "changes-requested"
    ]


def open_review_changes(note: Note, audits: list[Note], history: list[JsonObject]) -> list[JsonObject]:
    latest_decision = audits[-1].metadata.get("decision") if audits else None
    if note.review_state != "changes-requested" and latest_decision != "changes-requested":
        return []
    if history:
        return [history[-1]]
    return [
        {
            "review": None,
            "changes_requested": "Current note review_state is changes-requested without a direct change-request audit.",
        }
    ]


def review_triage(
    note: Note,
    *,
    schedule: JsonObject,
    audit_status: JsonObject,
    changes_requested: list[JsonObject],
    dependent_reviewed_knowledge: list[Note],
    dependent_contexts: list[Note],
) -> JsonObject:
    if changes_requested:
        action = "resolve-requested-changes"
    elif not audit_status["ok"]:
        action = "add-missing-review-audit"
    elif schedule["overdue"]:
        action = "review-overdue-note"
    elif schedule["due"]:
        action = "review-due-note"
    elif dependent_reviewed_knowledge or dependent_contexts:
        action = "inspect-downstream-impact-before-changing"
    else:
        action = "no-review-action"
    return {
        "status": schedule["status"],
        "recommended_action": action,
        "blocked_by_requested_changes": bool(changes_requested),
        "audit_gap": not audit_status["ok"],
        "downstream_impact_count": len(dependent_reviewed_knowledge) + len(dependent_contexts),
        "renewal_preserves_lifecycle": review_lifecycle_safety(note)["renewal_preserves_lifecycle"],
    }


def review_schedule_to_dict(
    vault: Vault,
    note: Note,
    audits: list[Note],
    *,
    due_on: str | None,
    review_due: bool,
) -> JsonObject:
    latest_audit = audits[-1] if audits else None
    schedule = review_due_details(note, due_on=due_on)
    return {
        "next_review": schedule["next_review"],
        "due_on": schedule["due_on"],
        "due": review_due,
        "overdue": schedule["overdue"],
        "days_overdue": schedule["days_overdue"],
        "status": schedule["status"],
        "audit_count": len(audits),
        "latest_audit": review_audit_to_dict(latest_audit, vault.root) if latest_audit else None,
    }


def review_audit_to_dict(note: Note, vault_root: Path) -> JsonObject:
    data = note_summary(note, vault_root)
    data["reviewer"] = json_safe(note.metadata.get("reviewer"))
    data["reviewed_at"] = json_safe(note.metadata.get("reviewed_at"))
    data["decision"] = json_safe(note.metadata.get("decision"))
    data["changes_requested"] = markdown_section(note.body, "Changes Requested")
    data["basis"] = markdown_section(note.body, "Basis")
    return data


def markdown_section(body: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<section>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(body)
    return match.group("section").strip() if match else ""


def redact_host_paths(metadata: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(metadata)
    for key in ("original_path", "bundle_path", "bundle_manifest_path"):
        value = redacted.get(key)
        if isinstance(value, str) and Path(value).is_absolute():
            redacted[key] = f"<local>/{Path(value).name}"
    return redacted


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value
