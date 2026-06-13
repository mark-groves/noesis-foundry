from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .vault import (
    CreatedNote,
    Note,
    Vault,
    approve_review,
    build_context,
    extract_evidence,
    filter_knowledge_by_scope,
    ingest_source,
    mark_memory_stale,
    promote_synthesis,
    propose_claim,
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

    def get_review_queue(self, vault_path: str | None = None) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        if issues:
            return validation_error(vault, issues)
        queue = vault.review_queue()
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "count": len(queue),
            "notes": [note_summary(note, vault.root) for note in queue],
        }

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
    ) -> JsonObject:
        vault = Vault.load(self.resolve_vault(vault_path))
        issues = vault.validate()
        if issues:
            return validation_error(vault, issues)
        knowledge = filter_knowledge_by_scope(vault.current_reviewed_knowledge(), scope)
        content = build_context(vault, scope=scope, purpose=purpose)
        return {
            "ok": True,
            "vault_path": str(vault.root),
            "scope": scope,
            "purpose": purpose,
            "reviewed_knowledge_count": len(knowledge),
            "reviewed_knowledge": [note_summary(note, vault.root) for note in knowledge],
            "content": content,
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
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        return self.write_result(
            write_context_note,
            self.resolve_vault(vault_path),
            scope=scope,
            purpose=purpose,
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
    def noesis_get_review_queue(vault_path: str | None = None) -> JsonObject:
        """List notes that still need review."""
        return handlers.get_review_queue(vault_path)

    @server.tool()
    def noesis_trace_lineage(note: str, vault_path: str | None = None) -> JsonObject:
        """Trace connected lineage for a Noesis note."""
        return handlers.trace_lineage(note, vault_path)

    @server.tool()
    def noesis_build_context(
        vault_path: str | None = None,
        scope: str | None = None,
        purpose: str | None = None,
    ) -> JsonObject:
        """Build operational context from current reviewed knowledge only."""
        return handlers.build_context(vault_path=vault_path, scope=scope, purpose=purpose)

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
        title: str | None = None,
        slug: str | None = None,
        next_review: str | None = None,
    ) -> JsonObject:
        """Write an operational context note from current reviewed knowledge."""
        return handlers.write_context(
            vault_path=vault_path,
            scope=scope,
            purpose=purpose,
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


def note_to_dict(note: Note, vault_root: Path) -> JsonObject:
    data = note_summary(note, vault_root)
    data["metadata"] = json_safe(note.metadata)
    data["body"] = note.body
    return data


def issue_to_dict(issue: Any, vault_root: Path) -> JsonObject:
    try:
        rel_path = issue.path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = str(issue.path)
    return {"path": rel_path, "message": issue.message}


def validation_error(vault: Vault, issues: list[Any]) -> JsonObject:
    return {
        "ok": False,
        "error": "vault validation failed",
        "vault_path": str(vault.root),
        "issue_count": len(issues),
        "issues": [issue_to_dict(issue, vault.root) for issue in issues],
    }


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
