from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any

from .vault import (
    ContextLineageSummary,
    ContextPackage,
    ContextSelection,
    CreatedNote,
    LIFECYCLE_STAGES,
    Note,
    REVIEW_STATES,
    TYPES,
    Vault,
    approve_review,
    compose_context,
    context_lifecycle_exclusion_kind,
    extract_evidence,
    import_source_bundle,
    ingest_source,
    is_excluded,
    mark_memory_stale,
    note_review_due,
    parse_review_date,
    promote_synthesis,
    propose_claim,
    review_cutoff_date,
    review_requires_audit,
    renew_review,
    request_review_changes,
    synthesize_claims,
    write_context_note,
)


JsonObject = dict[str, Any]


class NoesisMcpHandlers:
    def __init__(self, default_vault: Path | str | None = None) -> None:
        self.default_vault = Path(default_vault).expanduser().resolve() if default_vault else None

    def lint_vault(self, vault_path: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        doctor = vault.doctor()
        return {
            "ok": not issues,
            "vault_path": str(vault.root),
            "contract": doctor_payload(doctor),
            "compatible": doctor.compatible,
            "complete": doctor.complete,
            "ready_for_cli_mcp": doctor.ready_for_cli_mcp,
            "note_count": len(vault.notes),
            "issue_count": len(issues),
            "issues": [issue_to_dict(issue, vault.root) for issue in issues],
        }

    def search_notes(
        self,
        query: str = "",
        vault_path: str | None = None,
        note_type: str | None = None,
        lifecycle_stage: str | None = None,
        status: str | None = None,
        review_state: str | None = None,
        limit: int = 20,
    ) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        needle = query.casefold().strip()
        matches: list[Note] = []
        for note in vault.notes:
            if note_type and note.type != note_type:
                continue
            if lifecycle_stage and note.lifecycle_stage != lifecycle_stage:
                continue
            if status and note.status != status:
                continue
            if review_state and note.review_state != review_state:
                continue
            haystack = "\n".join(
                [
                    note.noesis_id,
                    note.title,
                    note.rel_path.as_posix(),
                    note.body,
                    json.dumps(json_safe(note.metadata), sort_keys=True),
                ]
            ).casefold()
            if needle and needle not in haystack:
                continue
            matches.append(note)

        bounded_limit = max(1, min(limit, 100))
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "count": min(len(matches), bounded_limit),
            "total_matches": len(matches),
            "notes": [note_summary(note, vault.root) for note in matches[:bounded_limit]],
        }

    def get_note(self, note: str, vault_path: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        found = vault.find_note(note)
        if found is None:
            return {"ok": False, "error": f"note not found: {note}", "vault_path": str(vault.root)}
        return {"ok": True, "vault_path": str(vault.root), "note": note_to_dict(found, vault.root)}

    def get_review_queue(
        self,
        vault_path: str | None = None,
        review_state: str | None = None,
        note_type: str | None = None,
        lifecycle_stage: str | None = None,
        due: bool = False,
        due_on: str | None = None,
    ) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        if issues:
            return validation_error(vault, issues)
        filter_error = review_filter_error(
            vault,
            review_state=review_state,
            note_type=note_type,
            lifecycle_stage=lifecycle_stage,
        )
        if filter_error:
            return filter_error
        due_filter = due or due_on is not None
        try:
            queue = vault.review_queue(
                review_state=review_state,
                note_type=note_type,
                lifecycle_stage=lifecycle_stage,
                due=due_filter,
                due_on=due_on,
            )
        except ValueError as exc:
            return review_error(vault, exc)
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "count": len(queue),
            "notes": [review_note_summary(note, vault, due_on=due_on) for note in queue],
            "filters": review_filters(
                review_state=review_state,
                note_type=note_type,
                lifecycle_stage=lifecycle_stage,
                due=due_filter,
                due_on=due_on,
            ),
        }

    def get_review_summary(self, vault_path: str | None = None, due_on: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        if issues:
            return validation_error(vault, issues)
        try:
            summary = vault.review_summary(due_on=due_on)
        except ValueError as exc:
            return review_error(vault, exc)
        return review_summary_to_dict(vault, summary, due_on=due_on)

    def show_review(self, note: str, vault_path: str | None = None, due_on: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        found = vault.find_note(note)
        if found is None:
            return {"ok": False, "error": f"note not found: {note}", "vault_path": str(vault.root)}
        try:
            return review_workbench_to_dict(vault, found, note_ref=note, due_on=due_on)
        except ValueError as exc:
            return review_error(vault, exc)

    def trace_lineage(self, note: str, vault_path: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        notes = vault.lineage(note)
        if not notes:
            return {"ok": False, "error": f"note not found or no lineage: {note}", "vault_path": str(vault.root)}
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "count": len(notes),
            "notes": [note_summary(lineage_note, vault.root) for lineage_note in notes],
        }

    def build_context(
        self,
        vault_path: str | None = None,
        scope: str | None = None,
        purpose: str | None = None,
        limit: int | None = None,
        max_chars: int | None = None,
        profile: str | None = None,
    ) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        if issues:
            return validation_error(vault, issues)
        try:
            package = compose_context(
                vault,
                scope=scope,
                purpose=purpose,
                limit=limit,
                max_chars=max_chars,
                profile=profile,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "vault_path": str(vault.root)}
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "scope": package.scope,
            "purpose": package.purpose,
            "profile": package.profile,
            "profile_description": package.profile_description,
            "limit": package.limit,
            "max_chars": package.max_chars,
            "requested_limit": package.requested_limit,
            "requested_max_chars": package.requested_max_chars,
            "applied_profile_defaults": list(package.applied_profile_defaults),
            "available_reviewed_knowledge_count": package.available_count,
            "reviewed_knowledge_count": len(package.reviewed_knowledge),
            "reviewed_knowledge": [note_summary(note, vault.root) for note in package.reviewed_knowledge],
            "selection": context_package_selection_payload(package, vault.root),
            "lineage_summaries": context_lineage_summary_payloads(package, vault.root),
            "content": package.content,
        }

    def ingest_source(
        self,
        source_file: str,
        title: str,
        vault_path: str | None = None,
        slug: str | None = None,
        source_type: str = "file",
        original_url: str = "unknown",
        author: str = "unknown",
        source_date: str = "unknown",
    ) -> JsonObject:
        return self.write_result(
            ingest_source,
            self.resolve_vault(vault_path),
            source_file,
            title,
            slug=slug,
            source_type=source_type,
            original_url=original_url,
            author=author,
            source_date=source_date,
        )

    def import_source_bundle(
        self,
        bundle_path: str,
        vault_path: str | None = None,
        manifest: str = "noesis-bundle.yaml",
        create_evidence: bool = False,
        allow_duplicates: bool = False,
    ) -> JsonObject:
        vault_root = self.resolve_vault(vault_path)
        try:
            imported = import_source_bundle(
                vault_root,
                bundle_path,
                manifest_name=manifest,
                create_evidence=create_evidence,
                allow_duplicates=allow_duplicates,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "vault_path": str(vault_root)}
        return source_bundle_import_to_dict(imported, vault_root)

    def create_evidence_draft(
        self,
        source: str,
        vault_path: str | None = None,
        title: str | None = None,
        evidence: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            extract_evidence,
            self.resolve_vault(vault_path),
            source,
            title=title,
            evidence=evidence,
            slug=slug,
        )

    def create_claim_draft(
        self,
        evidence: list[str],
        vault_path: str | None = None,
        title: str | None = None,
        claim: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            propose_claim,
            self.resolve_vault(vault_path),
            evidence,
            title=title,
            claim=claim,
            slug=slug,
        )

    def create_synthesis_draft(
        self,
        claim: list[str],
        vault_path: str | None = None,
        title: str | None = None,
        synthesis: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            synthesize_claims,
            self.resolve_vault(vault_path),
            claim,
            title=title,
            synthesis=synthesis,
            slug=slug,
        )

    def approve_review(
        self,
        note: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            approve_review,
            self.resolve_vault(vault_path),
            note,
            reviewer=reviewer,
            basis=basis,
            title=title,
            slug=slug,
            next_review=next_review,
        )

    def request_review_changes(
        self,
        note: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        changes_requested: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            request_review_changes,
            self.resolve_vault(vault_path),
            note,
            reviewer=reviewer,
            basis=basis,
            changes_requested=changes_requested,
            title=title,
            slug=slug,
        )

    def renew_review(
        self,
        note: str,
        next_review: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            renew_review,
            self.resolve_vault(vault_path),
            note,
            next_review=next_review,
            reviewer=reviewer,
            basis=basis,
            title=title,
            slug=slug,
        )

    def promote_synthesis(
        self,
        synthesis: str,
        vault_path: str | None = None,
        title: str | None = None,
        knowledge: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            promote_synthesis,
            self.resolve_vault(vault_path),
            synthesis,
            title=title,
            knowledge=knowledge,
            slug=slug,
            next_review=next_review,
        )

    def mark_memory_stale(
        self,
        note: str,
        reason: str,
        vault_path: str | None = None,
        superseded_by: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            mark_memory_stale,
            self.resolve_vault(vault_path),
            note,
            reason=reason,
            superseded_by=superseded_by,
            title=title,
            slug=slug,
        )

    def write_context(
        self,
        vault_path: str | None = None,
        scope: str | None = None,
        purpose: str | None = None,
        limit: int | None = None,
        max_chars: int | None = None,
        profile: str | None = None,
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            write_context_note,
            self.resolve_vault(vault_path),
            scope=scope,
            purpose=purpose,
            limit=limit,
            max_chars=max_chars,
            profile=profile,
            title=title,
            slug=slug,
            next_review=next_review,
        )

    def vault_summary(self, vault_path: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        type_counts: dict[str, int] = {}
        review_counts: dict[str, int] = {}
        for note in vault.notes:
            type_counts[note.type] = type_counts.get(note.type, 0) + 1
            review_counts[note.review_state] = review_counts.get(note.review_state, 0) + 1
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "note_count": len(vault.notes),
            "type_counts": dict(sorted(type_counts.items())),
            "review_state_counts": dict(sorted(review_counts.items())),
        }

    def resolve_vault(self, vault_path: str | None) -> Path:
        if vault_path:
            return Path(vault_path).expanduser().resolve()
        if self.default_vault is not None:
            return self.default_vault
        raise ValueError("vault_path is required when the server was not started with a default vault")

    def write_result(self, writer: Any, *args: Any, **kwargs: Any) -> JsonObject:
        vault_root = Path(args[0]).expanduser().resolve() if args else None
        try:
            created: CreatedNote = writer(*args, **kwargs)
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "vault_path": str(vault_root) if vault_root else None}
        return {"ok": True, "vault_path": str(vault_root), "created": created_note_to_dict(created, vault_root)}


def create_server(default_vault: Path | str | None = None) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError("The Noesis MCP server requires the 'mcp' package. Install this project with MCP dependencies.") from exc

    handlers = NoesisMcpHandlers(default_vault)
    server = FastMCP("Noesis Foundry", json_response=True)

    @server.tool()
    def noesis_lint_vault(vault_path: str | None = None) -> JsonObject:
        """Validate a Noesis vault and return structured validation issues."""
        return handlers.lint_vault(vault_path)

    @server.tool()
    def noesis_search_notes(
        query: str = "",
        vault_path: str | None = None,
        note_type: str | None = None,
        lifecycle_stage: str | None = None,
        status: str | None = None,
        review_state: str | None = None,
        limit: int = 20,
    ) -> JsonObject:
        """Search Noesis notes by text plus optional lifecycle metadata filters."""
        return handlers.search_notes(
            query=query,
            vault_path=vault_path,
            note_type=note_type,
            lifecycle_stage=lifecycle_stage,
            status=status,
            review_state=review_state,
            limit=limit,
        )

    @server.tool()
    def noesis_get_note(note: str, vault_path: str | None = None) -> JsonObject:
        """Fetch one Noesis note by id, filename stem, path, alias, or wikilink target."""
        return handlers.get_note(note, vault_path)

    @server.tool()
    def noesis_get_review_queue(
        vault_path: str | None = None,
        review_state: str | None = None,
        note_type: str | None = None,
        lifecycle_stage: str | None = None,
        due: bool = False,
        due_on: str | None = None,
    ) -> JsonObject:
        """List notes that still need review, with optional metadata and due-date filters."""
        return handlers.get_review_queue(
            vault_path=vault_path,
            review_state=review_state,
            note_type=note_type,
            lifecycle_stage=lifecycle_stage,
            due=due,
            due_on=due_on,
        )

    @server.tool()
    def noesis_get_review_summary(vault_path: str | None = None, due_on: str | None = None) -> JsonObject:
        """Summarize review states and scheduled next-review items."""
        return handlers.get_review_summary(vault_path=vault_path, due_on=due_on)

    @server.tool()
    def noesis_show_review(note: str, vault_path: str | None = None, due_on: str | None = None) -> JsonObject:
        """Inspect review state, lineage, audit records, support, and downstream impact for one note."""
        return handlers.show_review(note=note, vault_path=vault_path, due_on=due_on)

    @server.tool()
    def noesis_trace_lineage(note: str, vault_path: str | None = None) -> JsonObject:
        """Trace connected lineage for a Noesis note."""
        return handlers.trace_lineage(note, vault_path)

    @server.tool()
    def noesis_build_context(
        vault_path: str | None = None,
        scope: str | None = None,
        purpose: str | None = None,
        limit: int | None = None,
        max_chars: int | None = None,
        profile: str | None = None,
    ) -> JsonObject:
        """Build operational context from current reviewed knowledge only."""
        return handlers.build_context(
            vault_path=vault_path,
            scope=scope,
            purpose=purpose,
            limit=limit,
            max_chars=max_chars,
            profile=profile,
        )

    @server.tool()
    def noesis_ingest_source(
        source_file: str,
        title: str,
        vault_path: str | None = None,
        slug: str | None = None,
        source_type: str = "file",
        original_url: str = "unknown",
        author: str = "unknown",
        source_date: str = "unknown",
    ) -> JsonObject:
        """Copy raw source material into the vault and create a linked source note."""
        return handlers.ingest_source(
            source_file=source_file,
            title=title,
            vault_path=vault_path,
            slug=slug,
            source_type=source_type,
            original_url=original_url,
            author=author,
            source_date=source_date,
        )

    @server.tool()
    def noesis_import_source_bundle(
        bundle_path: str,
        vault_path: str | None = None,
        manifest: str = "noesis-bundle.yaml",
        create_evidence: bool = False,
        allow_duplicates: bool = False,
    ) -> JsonObject:
        """Import a local manifest-driven artifact bundle into source notes and optional evidence drafts."""
        return handlers.import_source_bundle(
            bundle_path=bundle_path,
            vault_path=vault_path,
            manifest=manifest,
            create_evidence=create_evidence,
            allow_duplicates=allow_duplicates,
        )

    @server.tool()
    def noesis_create_evidence_draft(
        source: str,
        vault_path: str | None = None,
        title: str | None = None,
        evidence: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Create a reviewable evidence draft linked to a source note."""
        return handlers.create_evidence_draft(source=source, vault_path=vault_path, title=title, evidence=evidence, slug=slug)

    @server.tool()
    def noesis_create_claim_draft(
        evidence: list[str],
        vault_path: str | None = None,
        title: str | None = None,
        claim: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Create a review-ready claim draft grounded in evidence notes."""
        return handlers.create_claim_draft(evidence=evidence, vault_path=vault_path, title=title, claim=claim, slug=slug)

    @server.tool()
    def noesis_create_synthesis_draft(
        claim: list[str],
        vault_path: str | None = None,
        title: str | None = None,
        synthesis: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Create a review-ready synthesis draft grounded in claim lineage."""
        return handlers.create_synthesis_draft(claim=claim, vault_path=vault_path, title=title, synthesis=synthesis, slug=slug)

    @server.tool()
    def noesis_approve_review(
        note: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        """Approve a reviewable note and write an audit review note."""
        return handlers.approve_review(
            note=note,
            vault_path=vault_path,
            reviewer=reviewer,
            basis=basis,
            title=title,
            slug=slug,
            next_review=next_review,
        )

    @server.tool()
    def noesis_request_review_changes(
        note: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        changes_requested: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Request review changes and write an audit review note."""
        return handlers.request_review_changes(
            note=note,
            vault_path=vault_path,
            reviewer=reviewer,
            basis=basis,
            changes_requested=changes_requested,
            title=title,
            slug=slug,
        )

    @server.tool()
    def noesis_renew_review(
        note: str,
        next_review: str,
        vault_path: str | None = None,
        reviewer: str = "unknown",
        basis: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Record a scheduled review audit and move the note's next_review date."""
        return handlers.renew_review(
            note=note,
            next_review=next_review,
            vault_path=vault_path,
            reviewer=reviewer,
            basis=basis,
            title=title,
            slug=slug,
        )

    @server.tool()
    def noesis_promote_synthesis(
        synthesis: str,
        vault_path: str | None = None,
        title: str | None = None,
        knowledge: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        """Promote an approved synthesis with review audit into reviewed knowledge."""
        return handlers.promote_synthesis(
            synthesis=synthesis,
            vault_path=vault_path,
            title=title,
            knowledge=knowledge,
            slug=slug,
            next_review=next_review,
        )

    @server.tool()
    def noesis_mark_memory_stale(
        note: str,
        reason: str,
        vault_path: str | None = None,
        superseded_by: str | None = None,
        title: str | None = None,
        slug: str | None = None,
    ) -> JsonObject:
        """Mark memory stale or superseded and update affected context exclusions."""
        return handlers.mark_memory_stale(
            note=note,
            reason=reason,
            vault_path=vault_path,
            superseded_by=superseded_by,
            title=title,
            slug=slug,
        )

    @server.tool()
    def noesis_write_context(
        vault_path: str | None = None,
        scope: str | None = None,
        purpose: str | None = None,
        limit: int | None = None,
        max_chars: int | None = None,
        profile: str | None = None,
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        """Write an operational context note from current reviewed knowledge."""
        return handlers.write_context(
            vault_path=vault_path,
            scope=scope,
            purpose=purpose,
            limit=limit,
            max_chars=max_chars,
            profile=profile,
            title=title,
            slug=slug,
            next_review=next_review,
        )

    @server.resource("noesis://vault/summary")
    def noesis_vault_summary() -> JsonObject:
        """Return a compact summary of the default Noesis vault."""
        return handlers.vault_summary()

    @server.resource("noesis://note/{note}")
    def noesis_note_resource(note: str) -> JsonObject:
        """Return one note from the default Noesis vault."""
        return handlers.get_note(note)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="noesis-mcp")
    parser.add_argument(
        "vault",
        nargs="?",
        type=Path,
        default=Path("examples/noesis-vault"),
        help="Default Noesis vault path for MCP resources and tools.",
    )
    args = parser.parse_args(argv)
    server = create_server(args.vault)
    server.run(transport="stdio")
    return 0


def note_summary(note: Note, vault_root: Path) -> JsonObject:
    return {
        "noesis_id": note.noesis_id,
        "title": note.title,
        "path": note.rel_path.as_posix(),
        "absolute_path": str(note.path),
        "type": note.type,
        "lifecycle_stage": note.lifecycle_stage,
        "status": note.status,
        "review_state": note.review_state,
        "confidence": json_safe(note.metadata.get("confidence")),
        "updated": json_safe(note.metadata.get("updated")),
        "next_review": json_safe(note.metadata.get("next_review")),
    }


def review_note_summary(note: Note, vault: Vault, *, due_on: str | None = None) -> JsonObject:
    data = note_summary(note, vault.root)
    audits = vault.review_audits_for(note)
    data["review_schedule"] = review_due_details(note, due_on=due_on)
    data["audit"] = {
        "count": len(audits),
        "requires_audit": review_requires_audit(note),
        "has_audit": bool(audits),
        "latest_decision": json_safe(audits[-1].metadata.get("decision")) if audits else None,
    }
    data["requested_changes"] = {
        "open": note.review_state == "changes-requested"
        or any(audit.metadata.get("decision") == "changes-requested" for audit in audits),
        "count": sum(1 for audit in audits if audit.metadata.get("decision") == "changes-requested"),
    }
    data["impact"] = review_impact_counts(vault, note)
    data["lifecycle_safety"] = review_lifecycle_safety(note)
    return data


def review_due_details(note: Note, *, due_on: str | None = None) -> JsonObject:
    cutoff = review_cutoff_date(due_on)
    next_review = parse_review_date(note.metadata.get("next_review"))
    due = next_review is not None and next_review <= cutoff
    overdue = next_review is not None and next_review < cutoff
    days_overdue = (cutoff - next_review).days if overdue and next_review is not None else 0
    if next_review is None:
        status = "unscheduled"
    elif overdue:
        status = "overdue"
    elif due:
        status = "due"
    else:
        status = "scheduled"
    return {
        "next_review": next_review.isoformat() if next_review else json_safe(note.metadata.get("next_review")),
        "due_on": cutoff.isoformat(),
        "due": due,
        "overdue": overdue,
        "days_overdue": days_overdue,
        "status": status,
    }


def review_impact_counts(vault: Vault, note: Note) -> JsonObject:
    return {
        "dependent_reviewed_knowledge": len(vault.dependent_reviewed_knowledge_for(note)),
        "dependent_contexts": len(vault.dependent_contexts_for(note)),
    }


def review_lifecycle_safety(note: Note) -> JsonObject:
    excluded = is_excluded(note)
    stale_memory = note.type == "stale-memory"
    return {
        "excluded_from_active_context": excluded,
        "stale_or_superseded_memory": stale_memory and excluded,
        "renewal_preserves_lifecycle": stale_memory and excluded,
    }


def review_triage(
    note: Note,
    *,
    schedule: JsonObject,
    audit_status: JsonObject,
    changes_requested: list[JsonObject],
    dependent_reviewed_knowledge: list[Note],
    dependent_contexts: list[Note],
) -> JsonObject:
    if changes_requested or note.review_state == "changes-requested":
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
        "blocked_by_requested_changes": bool(changes_requested) or note.review_state == "changes-requested",
        "audit_gap": not audit_status["ok"],
        "downstream_impact_count": len(dependent_reviewed_knowledge) + len(dependent_contexts),
        "renewal_preserves_lifecycle": review_lifecycle_safety(note)["renewal_preserves_lifecycle"],
    }


def context_package_selection_payload(package: ContextPackage, vault_root: Path) -> JsonObject:
    return {
        "included": [context_selection_payload(selection, vault_root) for selection in package.included],
        "excluded": [context_selection_payload(selection, vault_root) for selection in package.excluded],
        "scoped_out": [context_selection_payload(selection, vault_root) for selection in package.scoped_out],
        "budgeted_out": [context_selection_payload(selection, vault_root) for selection in package.budgeted_out],
        "lifecycle_excluded": [
            context_selection_payload(selection, vault_root) for selection in package.lifecycle_excluded
        ],
        "lifecycle_exclusion_summary": lifecycle_exclusion_summary(package.lifecycle_excluded),
    }


def context_selection_payload(selection: ContextSelection, vault_root: Path) -> JsonObject:
    payload = note_summary(selection.note, vault_root)
    payload.update(
        {
            "selection_status": selection.status,
            "selection_reason": selection.reason,
            "scope_score": selection.score,
            "content_chars": selection.content_chars,
            "lifecycle_exclusion_kind": (
                context_lifecycle_exclusion_kind(selection.note)
                if selection.status == "lifecycle_excluded"
                else None
            ),
        }
    )
    return payload


def lifecycle_exclusion_summary(selections: list[ContextSelection]) -> JsonObject:
    summary = {"stale": 0, "superseded": 0, "archived": 0, "excluded": 0}
    for selection in selections:
        kind = context_lifecycle_exclusion_kind(selection.note)
        summary[kind] = summary.get(kind, 0) + 1
    return summary


def context_lineage_summary_payloads(package: ContextPackage, vault_root: Path) -> list[JsonObject]:
    return [context_lineage_summary_payload(summary, vault_root) for summary in package.lineage_summaries]


def context_lineage_summary_payload(summary: ContextLineageSummary, vault_root: Path) -> JsonObject:
    stages = {
        "sources": summary.sources,
        "evidence": summary.evidence,
        "claims": summary.claims,
        "syntheses": summary.syntheses,
        "reviews": summary.reviews,
    }
    return {
        "reviewed_knowledge": note_summary(summary.reviewed_knowledge, vault_root),
        "counts": {stage: len(notes) for stage, notes in stages.items()},
        **{stage: [note_summary(note, vault_root) for note in notes] for stage, notes in stages.items()},
    }


def note_to_dict(note: Note, vault_root: Path) -> JsonObject:
    data = note_summary(note, vault_root)
    data["metadata"] = json_safe(note.metadata)
    data["body"] = note.body
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


def review_filter_error(
    vault: Vault,
    *,
    review_state: str | None = None,
    note_type: str | None = None,
    lifecycle_stage: str | None = None,
) -> JsonObject | None:
    allowed_types = TYPES - {"dashboard"}
    checks = (
        ("review_state", review_state, REVIEW_STATES),
        ("type", note_type, allowed_types),
        ("lifecycle_stage", lifecycle_stage, LIFECYCLE_STAGES),
    )
    for field, value, allowed in checks:
        if value is not None and value not in allowed:
            expected = ", ".join(sorted(allowed))
            return {
                "ok": False,
                "error": f"invalid {field}: {value}; expected one of: {expected}",
                "vault_path": str(vault.root),
                "field": field,
                "value": value,
                "expected": sorted(allowed),
            }
    return None


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


def review_workbench_to_dict(vault: Vault, note: Note, *, note_ref: str, due_on: str | None = None) -> JsonObject:
    audits = vault.review_audits_for(note)
    support = vault.support_notes_for(note)
    lineage = vault.lineage(note.noesis_id)
    review_due = note_review_due(note, due_on=due_on)
    schedule = review_due_details(note, due_on=due_on)
    dependent_reviewed_knowledge = vault.dependent_reviewed_knowledge_for(note)
    dependent_contexts = vault.dependent_contexts_for(note)
    changes_requested = [
        {
            "review": note_summary(audit, vault.root),
            "changes_requested": markdown_section(audit.body, "Changes Requested"),
        }
        for audit in audits
        if audit.metadata.get("decision") == "changes-requested"
    ]
    requires_audit = review_requires_audit(note)
    audit_status = {
        "requires_audit": requires_audit,
        "has_audit": bool(audits),
        "ok": (not requires_audit) or bool(audits),
    }
    return {
        "ok": True,
        "vault_path": str(vault.root),
        "note_ref": note_ref,
        "note": note_to_dict(note, vault.root),
        "review_due": review_due,
        "review_schedule": review_schedule_to_dict(vault, note, audits, due_on=due_on, review_due=review_due),
        "triage": review_triage(
            note,
            schedule=schedule,
            audit_status=audit_status,
            changes_requested=changes_requested,
            dependent_reviewed_knowledge=dependent_reviewed_knowledge,
            dependent_contexts=dependent_contexts,
        ),
        "audit_status": audit_status,
        "audit_records": [review_audit_to_dict(audit, vault.root) for audit in audits],
        "support": {
            key: [note_summary(support_note, vault.root) for support_note in notes]
            for key, notes in support.items()
        },
        "changes_requested": changes_requested,
        "impact": {
            "dependent_reviewed_knowledge": [
                note_summary(dependent, vault.root)
                for dependent in dependent_reviewed_knowledge
            ],
            "dependent_contexts": [
                note_summary(dependent, vault.root)
                for dependent in dependent_contexts
            ],
            "counts": {
                "dependent_reviewed_knowledge": len(dependent_reviewed_knowledge),
                "dependent_contexts": len(dependent_contexts),
            },
        },
        "lifecycle_safety": review_lifecycle_safety(note),
        "lineage": [note_summary(lineage_note, vault.root) for lineage_note in lineage],
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
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        return ""
    return match.group("section").strip()


def issue_to_dict(issue: Any, vault_root: Path) -> JsonObject:
    try:
        rel_path = issue.path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = str(issue.path)
    return {"path": rel_path, "message": issue.message}


def validation_error(vault: Vault, issues: list[Any]) -> JsonObject:
    doctor = vault.doctor()
    return {
        "ok": False,
        "error": "vault validation failed",
        "vault_path": str(vault.root),
        "contract": doctor_payload(doctor),
        "compatible": doctor.compatible,
        "complete": doctor.complete,
        "ready_for_cli_mcp": doctor.ready_for_cli_mcp,
        "issue_count": len(issues),
        "issues": [issue_to_dict(issue, vault.root) for issue in issues],
    }


def review_error(vault: Vault, error: ValueError) -> JsonObject:
    return {"ok": False, "error": str(error), "vault_path": str(vault.root)}


def doctor_payload(doctor: Any) -> JsonObject:
    contract_version = doctor.contract.get("contract_version")
    return {
        "path": str(doctor.contract_path),
        "present": doctor.contract_path.exists(),
        "version": str(contract_version) if contract_version is not None else None,
        "supported": doctor.compatible,
        "metadata": json_safe(doctor.contract),
        "issues": [issue_to_dict(issue, doctor.root) for issue in doctor.contract_issues],
    }


def created_note_to_dict(created: CreatedNote, vault_root: Path | None) -> JsonObject:
    data = json_safe(asdict(created))
    if vault_root is not None:
        try:
            data["path"] = created.path.relative_to(vault_root).as_posix()
        except ValueError:
            data["path"] = str(created.path)
    return data


def source_capture_result_to_dict(result: Any, vault_root: Path) -> JsonObject:
    payload: JsonObject = {
        "status": result.status,
        "source_file": str(result.source_file),
        "title": result.title,
        "content_hash": result.content_hash,
    }
    if result.note is not None:
        payload["note"] = created_note_to_dict(result.note, vault_root)
    if result.raw_path is not None:
        try:
            payload["raw_path"] = result.raw_path.relative_to(vault_root).as_posix()
        except ValueError:
            payload["raw_path"] = str(result.raw_path)
    if result.evidence_note is not None:
        payload["evidence_note"] = created_note_to_dict(result.evidence_note, vault_root)
    if result.existing_note_id is not None:
        payload["existing_note_id"] = result.existing_note_id
    if result.existing_note_path is not None:
        try:
            payload["existing_note_path"] = result.existing_note_path.relative_to(vault_root).as_posix()
        except ValueError:
            payload["existing_note_path"] = str(result.existing_note_path)
    if result.reason is not None:
        payload["reason"] = result.reason
    return payload


def source_bundle_import_to_dict(imported: Any, vault_root: Path) -> JsonObject:
    return {
        "ok": True,
        "vault_path": str(vault_root),
        "bundle_id": imported.bundle_id,
        "title": imported.title,
        "bundle_path": str(imported.bundle_path),
        "manifest_path": str(imported.manifest_path),
        "manifest_hash": imported.manifest_hash,
        "artifact_count": len(imported.results),
        "created_count": sum(1 for result in imported.results if result.status == "created"),
        "skipped_count": sum(1 for result in imported.results if result.status == "skipped"),
        "results": [source_capture_result_to_dict(result, vault_root) for result in imported.results],
    }


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


if __name__ == "__main__":
    raise SystemExit(main())
