from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .mcp_server import (
    issue_to_dict,
    json_safe,
    note_summary,
    review_filters,
    review_note_summary,
    review_summary_to_dict,
    review_workbench_to_dict,
)
from .vault import (
    CONTEXT_PROFILE_NAMES,
    ContextPackage,
    ContextLineageSummary,
    ContextSelection,
    LIFECYCLE_STAGES,
    REVIEW_STATES,
    SOURCE_BUNDLE_SCHEMA_KIND,
    TYPES,
    Vault,
    approve_review,
    build_context,
    compose_context,
    context_lifecycle_exclusion_kind,
    extract_evidence,
    filter_knowledge_by_scope,
    import_source_bundle,
    ingest_sources,
    init_vault,
    mark_memory_stale,
    promote_synthesis,
    propose_claim,
    renew_review,
    request_review_changes,
    synthesize_claims,
    write_context_note,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noesis")
    subcommands = parser.add_subparsers(dest="command", required=True)

    vault = subcommands.add_parser("vault", help="Manage a Noesis vault")
    vault_commands = vault.add_subparsers(dest="vault_command", required=True)

    vault_init = vault_commands.add_parser("init", help="Initialize a Noesis vault")
    vault_init.add_argument("path", type=Path)
    vault_init.add_argument("--force", action="store_true", help="Overwrite existing scaffold files")
    vault_init.set_defaults(func=cmd_vault_init)

    validate = vault_commands.add_parser("validate", help="Validate a Noesis vault")
    validate.add_argument("path", type=Path)
    validate.add_argument("--json", action="store_true", help="Write structured JSON")
    validate.set_defaults(func=cmd_vault_validate)

    doctor = vault_commands.add_parser("doctor", help="Diagnose vault compatibility and readiness")
    doctor.add_argument("path", type=Path)
    doctor.add_argument("--json", action="store_true", help="Write structured JSON")
    doctor.set_defaults(func=cmd_vault_doctor)

    ingest = subcommands.add_parser("ingest", help="Ingest source material")
    ingest_commands = ingest.add_subparsers(dest="ingest_command", required=True)
    source = ingest_commands.add_parser("source", help="Copy a raw source and create a source note")
    source.add_argument("--vault", type=Path, required=True)
    source_input = source.add_mutually_exclusive_group(required=True)
    source_input.add_argument("--file", type=Path, nargs="+")
    source_input.add_argument("--directory", type=Path)
    source.add_argument("--recursive", action="store_true", help="Include files below subdirectories")
    source.add_argument("--pattern", action="append", help="Glob pattern for --directory; may be repeated")
    source.add_argument("--title", default=None)
    source.add_argument("--slug", default=None)
    source.add_argument("--source-type", default="file")
    source.add_argument("--original-url", default="unknown")
    source.add_argument("--author", default="unknown")
    source.add_argument("--source-date", default="unknown")
    source.add_argument("--allow-duplicates", action="store_true")
    source.add_argument("--evidence-drafts", action="store_true", help="Create one reviewable evidence draft per new source")
    source.add_argument("--json", action="store_true", help="Write structured JSON")
    source.set_defaults(func=cmd_ingest_source)

    bundle = ingest_commands.add_parser("bundle", help="Import a local manifest-driven source bundle")
    bundle.add_argument("--vault", type=Path, required=True)
    bundle.add_argument("path", type=Path, help="Bundle directory or manifest file")
    bundle.add_argument(
        "--manifest",
        default="noesis-bundle.yaml",
        help="Manifest filename when path is a directory",
    )
    bundle.add_argument("--allow-duplicates", action="store_true")
    bundle.add_argument("--evidence-drafts", action="store_true", help="Create one reviewable evidence draft per new source")
    bundle.add_argument("--json", action="store_true", help="Write structured JSON")
    bundle.set_defaults(func=cmd_ingest_bundle)

    extract = subcommands.add_parser("extract", help="Extract lifecycle drafts")
    extract_commands = extract.add_subparsers(dest="extract_command", required=True)
    evidence = extract_commands.add_parser("evidence", help="Create a reviewable evidence draft")
    evidence.add_argument("--vault", type=Path, required=True)
    evidence.add_argument("--source", required=True)
    evidence.add_argument("--title", default=None)
    evidence.add_argument("--evidence", default=None)
    evidence.add_argument("--slug", default=None)
    evidence.set_defaults(func=cmd_extract_evidence)

    propose = subcommands.add_parser("propose", help="Propose lifecycle drafts")
    propose_commands = propose.add_subparsers(dest="propose_command", required=True)
    claim = propose_commands.add_parser("claim", help="Create a review-ready claim draft")
    claim.add_argument("--vault", type=Path, required=True)
    claim.add_argument("--evidence", action="append", required=True)
    claim.add_argument("--title", default=None)
    claim.add_argument("--claim", default=None)
    claim.add_argument("--slug", default=None)
    claim.set_defaults(func=cmd_propose_claim)

    synthesize = subcommands.add_parser("synthesize", help="Create a synthesis draft from claims")
    synthesize.add_argument("--vault", type=Path, required=True)
    synthesize.add_argument("--claim", action="append", required=True)
    synthesize.add_argument("--title", default=None)
    synthesize.add_argument("--synthesis", default=None)
    synthesize.add_argument("--slug", default=None)
    synthesize.set_defaults(func=cmd_synthesize)

    review = subcommands.add_parser("review", help="Review workflows")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    queue = review_commands.add_parser("queue", help="List notes that need review")
    queue.add_argument("--vault", type=Path, required=True)
    queue.add_argument("--review-state", choices=sorted(REVIEW_STATES), default=None)
    queue.add_argument("--type", dest="note_type", choices=sorted(TYPES - {"dashboard"}), default=None)
    queue.add_argument("--stage", dest="lifecycle_stage", choices=sorted(LIFECYCLE_STAGES), default=None)
    queue.add_argument("--due", action="store_true", help="Only include notes with next_review on or before today")
    queue.add_argument("--due-on", default=None, help="Use this YYYY-MM-DD cutoff for --due")
    queue.add_argument("--json", action="store_true", help="Write structured JSON")
    queue.set_defaults(func=cmd_review_queue)

    summary = review_commands.add_parser("summary", help="Summarize review states and scheduled reviews")
    summary.add_argument("--vault", type=Path, required=True)
    summary.add_argument("--due-on", default=None, help="Use this YYYY-MM-DD cutoff for due review counts")
    summary.add_argument("--json", action="store_true", help="Write structured JSON")
    summary.set_defaults(func=cmd_review_summary)

    show = review_commands.add_parser("show", help="Inspect one note's review state, support, audit, and impact")
    show.add_argument("note")
    show.add_argument("--vault", type=Path, required=True)
    show.add_argument("--due-on", default=None, help="Use this YYYY-MM-DD cutoff for due status")
    show.add_argument("--json", action="store_true", help="Write structured JSON")
    show.set_defaults(func=cmd_review_show)

    approve = review_commands.add_parser("approve", help="Approve a reviewable note and write an audit review")
    approve.add_argument("note")
    approve.add_argument("--vault", type=Path, required=True)
    approve.add_argument("--reviewer", default="unknown")
    approve.add_argument("--basis", default=None)
    approve.add_argument("--title", default=None)
    approve.add_argument("--slug", default=None)
    approve.add_argument("--next-review", default=None)
    approve.set_defaults(func=cmd_review_approve)

    request_changes = review_commands.add_parser("request-changes", help="Request changes and write an audit review")
    request_changes.add_argument("note")
    request_changes.add_argument("--vault", type=Path, required=True)
    request_changes.add_argument("--reviewer", default="unknown")
    request_changes.add_argument("--basis", default=None)
    request_changes.add_argument("--changes-requested", default=None)
    request_changes.add_argument("--title", default=None)
    request_changes.add_argument("--slug", default=None)
    request_changes.set_defaults(func=cmd_review_request_changes)

    renew = review_commands.add_parser("renew", help="Record a scheduled review audit and reschedule a note")
    renew.add_argument("note")
    renew.add_argument("--vault", type=Path, required=True)
    renew.add_argument("--reviewer", default="unknown")
    renew.add_argument("--basis", default=None)
    renew.add_argument("--title", default=None)
    renew.add_argument("--slug", default=None)
    renew.add_argument("--next-review", required=True)
    renew.set_defaults(func=cmd_review_renew)

    knowledge = subcommands.add_parser("knowledge", help="Reviewed knowledge workflows")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", required=True)
    promote = knowledge_commands.add_parser("promote", help="Promote an approved synthesis to reviewed knowledge")
    promote.add_argument("--vault", type=Path, required=True)
    promote.add_argument("--synthesis", required=True)
    promote.add_argument("--title", default=None)
    promote.add_argument("--knowledge", default=None)
    promote.add_argument("--slug", default=None)
    promote.add_argument("--next-review", default=None)
    promote.set_defaults(func=cmd_knowledge_promote)

    memory = subcommands.add_parser("memory", help="Memory lifecycle workflows")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    stale = memory_commands.add_parser("stale", help="Mark memory stale or superseded")
    stale.add_argument("note")
    stale.add_argument("--vault", type=Path, required=True)
    stale.add_argument("--reason", required=True)
    stale.add_argument("--superseded-by", default=None)
    stale.add_argument("--title", default=None)
    stale.add_argument("--slug", default=None)
    stale.set_defaults(func=cmd_memory_stale)

    trace = subcommands.add_parser("trace", help="Trace one note's lineage")
    trace.add_argument("note", help="noesis_id, filename stem, or wikilink")
    trace.add_argument("--vault", type=Path, required=True)
    trace.add_argument("--json", action="store_true", help="Write structured JSON")
    trace.set_defaults(func=cmd_trace)

    context = subcommands.add_parser("context", help="Operational context workflows")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    build = context_commands.add_parser("build", help="Build context from reviewed knowledge")
    build.add_argument("--vault", type=Path, required=True)
    build.add_argument("--scope", default=None)
    build.add_argument("--purpose", default=None)
    build.add_argument("--profile", choices=sorted(CONTEXT_PROFILE_NAMES), default=None)
    build.add_argument("--limit", type=int, default=None, help="Maximum reviewed knowledge notes to include")
    build.add_argument("--max-chars", type=int, default=None, help="Approximate maximum reviewed knowledge body characters")
    build.add_argument("--output", type=Path, default=None)
    build.add_argument("--json", action="store_true", help="Write structured JSON")
    build.set_defaults(func=cmd_context_build)

    explain = context_commands.add_parser("explain", help="Explain context selection and lifecycle exclusions")
    explain.add_argument("--vault", type=Path, required=True)
    explain.add_argument("--scope", default=None)
    explain.add_argument("--purpose", default=None)
    explain.add_argument("--profile", choices=sorted(CONTEXT_PROFILE_NAMES), default=None)
    explain.add_argument("--limit", type=int, default=None, help="Maximum reviewed knowledge notes to include")
    explain.add_argument("--max-chars", type=int, default=None, help="Approximate maximum reviewed knowledge body characters")
    explain.add_argument("--json", action="store_true", help="Write structured JSON")
    explain.set_defaults(func=cmd_context_explain)

    write = context_commands.add_parser("write", help="Write an operational context note")
    write.add_argument("--vault", type=Path, required=True)
    write.add_argument("--scope", default=None)
    write.add_argument("--purpose", default=None)
    write.add_argument("--profile", choices=sorted(CONTEXT_PROFILE_NAMES), default=None)
    write.add_argument("--limit", type=int, default=None, help="Maximum reviewed knowledge notes to include")
    write.add_argument("--max-chars", type=int, default=None, help="Approximate maximum reviewed knowledge body characters")
    write.add_argument("--title", default=None)
    write.add_argument("--slug", default=None)
    write.add_argument("--next-review", default=None)
    write.set_defaults(func=cmd_context_write)

    return parser


def cmd_vault_init(args: argparse.Namespace) -> int:
    created = init_vault(args.path, force=args.force)
    print(f"initialized {Path(args.path).resolve()}")
    print(f"created_or_checked {len(created)} paths")
    return 0


def cmd_vault_validate(args: argparse.Namespace) -> int:
    vault = Vault.load(args.path)
    issues = vault.validate()
    doctor = vault.doctor()
    if args.json:
        write_json(
            {
                "ok": not issues,
                "vault_path": str(vault.root),
                "contract": doctor_payload(doctor)["contract"],
                "compatible": doctor.compatible,
                "complete": doctor.complete,
                "ready_for_cli_mcp": doctor.ready_for_cli_mcp,
                "note_count": len(vault.notes),
                "issue_count": len(issues),
                "issues": [issue_to_dict(issue, vault.root) for issue in issues],
            }
        )
        return 1 if issues else 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        print(f"validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1
    print(f"validation ok: {vault.root}")
    print(f"contract: v{doctor.contract.get('contract_version')}")
    print(f"notes: {len(vault.notes)}")
    return 0


def cmd_vault_doctor(args: argparse.Namespace) -> int:
    vault = Vault.load(args.path)
    doctor = vault.doctor()
    payload = doctor_payload(doctor)
    if args.json:
        write_json(payload)
        return 0 if doctor.ready_for_cli_mcp else 1

    status = "ready" if doctor.ready_for_cli_mcp else "not ready"
    print(f"vault: {doctor.root}")
    print(f"status: {status}")
    print(f"compatible: {format_bool(doctor.compatible)}")
    print(f"complete: {format_bool(doctor.complete)}")
    print(f"ready_for_cli_mcp: {format_bool(doctor.ready_for_cli_mcp)}")
    contract_version = doctor.contract.get("contract_version", "unknown")
    print(f"contract: v{contract_version}")
    print(f"notes: {doctor.note_count}")
    if doctor.validation_issues:
        print(f"issues: {len(doctor.validation_issues)}", file=sys.stderr)
        for issue in doctor.validation_issues:
            print(f"ERROR {issue.format(doctor.root)}", file=sys.stderr)
        return 1
    print("issues: 0")
    return 0


def cmd_ingest_source(args: argparse.Namespace) -> int:
    try:
        source_files = collect_ingest_source_files(args)
        results = ingest_sources(
            args.vault,
            source_files,
            source_root=args.directory,
            title=args.title,
            slug=args.slug,
            source_type=args.source_type,
            original_url=args.original_url,
            author=args.author,
            source_date=args.source_date,
            allow_duplicates=args.allow_duplicates,
            create_evidence=args.evidence_drafts,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    if args.json:
        write_json(
            {
                "ok": True,
                "vault_path": str(Path(args.vault).expanduser().resolve()),
                "created_count": sum(1 for result in results if result.status == "created"),
                "skipped_count": sum(1 for result in results if result.status == "skipped"),
                "results": [source_capture_result_payload(result) for result in results],
            }
        )
        return 0

    if len(results) == 1:
        result = results[0]
        if result.note is not None:
            print(f"created {result.note.note_id}\t{result.note.path}")
            if result.evidence_note is not None:
                print(f"created {result.evidence_note.note_id}\t{result.evidence_note.path}")
        else:
            print(f"skipped {result.existing_note_id}\t{result.reason}\t{result.source_file}")
        return 0

    created_count = sum(1 for result in results if result.status == "created")
    skipped_count = sum(1 for result in results if result.status == "skipped")
    print(f"ingest summary: created={created_count} skipped={skipped_count}")
    for result in results:
        if result.note is not None:
            print(f"created {result.note.note_id}\t{result.note.path}\t{result.source_file}")
            if result.evidence_note is not None:
                print(f"created {result.evidence_note.note_id}\t{result.evidence_note.path}\tevidence")
        else:
            print(f"skipped {result.existing_note_id}\t{result.reason}\t{result.source_file}")
    return 0


def cmd_ingest_bundle(args: argparse.Namespace) -> int:
    try:
        imported = import_source_bundle(
            args.vault,
            args.path,
            manifest_name=args.manifest,
            create_evidence=args.evidence_drafts,
            allow_duplicates=args.allow_duplicates,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    if args.json:
        write_json(source_bundle_import_payload(imported, args.vault))
        return 0

    created_count = sum(1 for result in imported.results if result.status == "created")
    skipped_count = sum(1 for result in imported.results if result.status == "skipped")
    print(f"bundle import: {imported.bundle_id}")
    print(f"manifest: {imported.manifest_path}")
    print(f"ingest summary: created={created_count} skipped={skipped_count}")
    for result in imported.results:
        if result.note is not None:
            print(f"created {result.note.note_id}\t{result.note.path}\t{result.source_file}")
            if result.evidence_note is not None:
                print(f"created {result.evidence_note.note_id}\t{result.evidence_note.path}\tevidence")
        else:
            print(f"skipped {result.existing_note_id}\t{result.reason}\t{result.source_file}")
    return 0


def collect_ingest_source_files(args: argparse.Namespace) -> list[Path]:
    if args.file:
        if args.recursive:
            raise ValueError("--recursive can only be used with --directory")
        if args.pattern:
            raise ValueError("--pattern can only be used with --directory")
        return list(args.file)

    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(f"source directory does not exist: {args.directory}")
    patterns = args.pattern or ["*"]
    files: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = directory.rglob(pattern) if args.recursive else directory.glob(pattern)
        for path in matches:
            resolved = path.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            files.append(resolved)
            seen.add(resolved)
    return sorted(files, key=lambda path: path.relative_to(directory).as_posix())


def source_capture_result_payload(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": result.status,
        "source_file": str(result.source_file),
        "title": result.title,
        "content_hash": result.content_hash,
    }
    if result.note is not None:
        payload["note_id"] = result.note.note_id
        payload["note_path"] = str(result.note.path)
    if result.raw_path is not None:
        payload["raw_path"] = str(result.raw_path)
    if result.evidence_note is not None:
        payload["evidence_note_id"] = result.evidence_note.note_id
        payload["evidence_note_path"] = str(result.evidence_note.path)
    if result.existing_note_id is not None:
        payload["existing_note_id"] = result.existing_note_id
    if result.existing_note_path is not None:
        payload["existing_note_path"] = str(result.existing_note_path)
    if result.reason is not None:
        payload["reason"] = result.reason
    return payload


def source_bundle_import_payload(imported: Any, vault_path: Path | str) -> dict[str, Any]:
    return {
        "ok": True,
        "vault_path": str(Path(vault_path).expanduser().resolve()),
        "bundle_id": imported.bundle_id,
        "title": imported.title,
        "schema": SOURCE_BUNDLE_SCHEMA_KIND,
        "schema_version": imported.schema_version,
        "bundle_path": str(imported.bundle_path),
        "manifest_path": str(imported.manifest_path),
        "manifest_hash": imported.manifest_hash,
        "artifact_count": len(imported.results),
        "created_count": sum(1 for result in imported.results if result.status == "created"),
        "skipped_count": sum(1 for result in imported.results if result.status == "skipped"),
        "results": [source_capture_result_payload(result) for result in imported.results],
    }


def cmd_extract_evidence(args: argparse.Namespace) -> int:
    try:
        created = extract_evidence(
            args.vault,
            args.source,
            title=args.title,
            evidence=args.evidence,
            slug=args.slug,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_propose_claim(args: argparse.Namespace) -> int:
    try:
        created = propose_claim(
            args.vault,
            args.evidence,
            title=args.title,
            claim=args.claim,
            slug=args.slug,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    try:
        created = synthesize_claims(
            args.vault,
            args.claim,
            title=args.title,
            synthesis=args.synthesis,
            slug=args.slug,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_review_queue(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    issues = vault.validate()
    due_filter = args.due or args.due_on is not None
    if args.json:
        if issues:
            write_json(validation_error_payload(vault, issues))
            return 1
        try:
            queue = vault.review_queue(
                review_state=args.review_state,
                note_type=args.note_type,
                lifecycle_stage=args.lifecycle_stage,
                due=due_filter,
                due_on=args.due_on,
            )
        except ValueError as exc:
            write_json(review_error_payload(vault, exc))
            return 1
        write_json(
            {
                "ok": True,
                "vault_path": str(vault.root),
                "count": len(queue),
                "notes": [review_note_summary(note, vault, due_on=args.due_on) for note in queue],
                "filters": review_filters(
                    review_state=args.review_state,
                    note_type=args.note_type,
                    lifecycle_stage=args.lifecycle_stage,
                    due=due_filter,
                    due_on=args.due_on,
                ),
            }
        )
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        print(f"validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1
    try:
        queue = vault.review_queue(
            review_state=args.review_state,
            note_type=args.note_type,
            lifecycle_stage=args.lifecycle_stage,
            due=due_filter,
            due_on=args.due_on,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    if not queue:
        print("review queue empty")
        return 0
    for note in queue:
        next_review = note.metadata.get("next_review", "")
        governance = review_note_summary(note, vault, due_on=args.due_on)
        schedule = governance["review_schedule"]
        impact = governance["impact"]
        print(
            "\t".join(
                [
                    note.noesis_id,
                    note.rel_path.as_posix(),
                    note.review_state,
                    note.status,
                    str(next_review),
                    schedule["status"],
                    f"impact:{impact['dependent_reviewed_knowledge']}/{impact['dependent_contexts']}",
                    note.title,
                ]
            )
        )
    return 0


def cmd_review_summary(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    issues = vault.validate()
    if args.json:
        if issues:
            write_json(validation_error_payload(vault, issues))
            return 1
        try:
            summary = vault.review_summary(due_on=args.due_on)
        except ValueError as exc:
            write_json(review_error_payload(vault, exc))
            return 1
        write_json(review_summary_to_dict(vault, summary, due_on=args.due_on))
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        print(f"validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1
    try:
        summary = vault.review_summary(due_on=args.due_on)
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print("review summary")
    print(f"pending: {summary['pending_count']}")
    print(f"due: {summary['due_count']}")
    print(f"overdue: {summary['overdue_count']}")
    print(f"requested changes: {summary['requested_changes_count']}")
    print(f"audit gaps: {summary['audit_gap_count']}")
    print("review states:")
    for state, count in summary["review_state_counts"].items():
        print(f"  {state}: {count}")
    if summary["overdue_notes"]:
        print("overdue:")
        for note in summary["overdue_notes"]:
            next_review = note.metadata.get("next_review", "")
            print(
                "\t".join(
                    [
                        str(next_review),
                        note.noesis_id,
                        note.rel_path.as_posix(),
                        note.review_state,
                        note.title,
                    ]
                )
            )
    if summary["requested_changes_notes"]:
        print("requested changes:")
        for note in summary["requested_changes_notes"]:
            print(
                "\t".join(
                    [
                        note.noesis_id,
                        note.rel_path.as_posix(),
                        note.status,
                        note.title,
                    ]
                )
            )
    if summary["audit_gap_notes"]:
        print("audit gaps:")
        for note in summary["audit_gap_notes"]:
            print(
                "\t".join(
                    [
                        note.noesis_id,
                        note.rel_path.as_posix(),
                        note.review_state,
                        note.title,
                    ]
                )
            )
    if summary["next_review_notes"]:
        print("next review:")
        for note in summary["next_review_notes"]:
            print(
                "\t".join(
                    [
                        str(note.metadata.get("next_review", "")),
                        note.noesis_id,
                        note.rel_path.as_posix(),
                        note.review_state,
                        note.title,
                    ]
                )
            )
    return 0


def cmd_review_show(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    note = vault.find_note(args.note)
    if note is None:
        if args.json:
            write_json({"ok": False, "error": f"note not found: {args.note}", "vault_path": str(vault.root)})
        else:
            print(f"note not found: {args.note}", file=sys.stderr)
        return 1
    try:
        payload = review_workbench_to_dict(vault, note, note_ref=args.note, due_on=args.due_on)
    except ValueError as exc:
        if args.json:
            write_json(review_error_payload(vault, exc))
        else:
            print(f"ERROR {exc}", file=sys.stderr)
        return 1
    if args.json:
        write_json(payload)
        return 0
    print(f"review workbench: {note.title}")
    print(f"id: {note.noesis_id}")
    print(f"path: {note.rel_path.as_posix()}")
    print(f"state: {note.status} / {note.review_state}")
    print(f"confidence: {note.metadata.get('confidence', 'unknown')}")
    schedule = payload["review_schedule"]
    print(f"next_review: {schedule.get('next_review') or 'not scheduled'}")
    print(f"review_due: {str(schedule['due']).lower()}")
    print(f"schedule_status: {schedule['status']}")
    if schedule["overdue"]:
        print(f"days_overdue: {schedule['days_overdue']}")
    triage = payload["triage"]
    print(f"recommended_action: {triage['recommended_action']}")
    lifecycle_safety = payload["lifecycle_safety"]
    if lifecycle_safety["stale_or_superseded_memory"]:
        print(
            "lifecycle_safety: "
            "stale/superseded memory remains excluded from active context; renewal preserves lifecycle"
        )
    latest_audit = schedule.get("latest_audit")
    if latest_audit:
        print(
            "latest_audit: "
            f"{latest_audit.get('reviewed_at', 'unknown')} "
            f"{latest_audit.get('decision', 'unknown')} "
            f"{latest_audit['noesis_id']}"
        )
    audit_status = payload["audit_status"]
    print(
        "audit: "
        f"{len(payload['audit_records'])} record(s), "
        f"required={str(audit_status['requires_audit']).lower()}, "
        f"ok={str(audit_status['ok']).lower()}"
    )
    print_audit_history(payload["audit_records"])
    print_section_notes("support", payload["support"])
    print_flat_notes("dependent reviewed knowledge", payload["impact"]["dependent_reviewed_knowledge"])
    print_flat_notes("dependent contexts", payload["impact"]["dependent_contexts"])
    if payload["changes_requested"]:
        print("changes requested:")
        for change in payload["changes_requested"]:
            review = change["review"]
            review_id = review["noesis_id"] if review is not None else "propagated-change-request"
            print(f"  {review_id}: {change['changes_requested']}")
    print_flat_notes("lineage", payload["lineage"])
    return 0


def cmd_review_approve(args: argparse.Namespace) -> int:
    try:
        created = approve_review(
            args.vault,
            args.note,
            reviewer=args.reviewer,
            basis=args.basis,
            title=args.title,
            slug=args.slug,
            next_review=args.next_review,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_review_request_changes(args: argparse.Namespace) -> int:
    try:
        created = request_review_changes(
            args.vault,
            args.note,
            reviewer=args.reviewer,
            basis=args.basis,
            changes_requested=args.changes_requested,
            title=args.title,
            slug=args.slug,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_review_renew(args: argparse.Namespace) -> int:
    try:
        created = renew_review(
            args.vault,
            args.note,
            reviewer=args.reviewer,
            basis=args.basis,
            title=args.title,
            slug=args.slug,
            next_review=args.next_review,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_knowledge_promote(args: argparse.Namespace) -> int:
    try:
        created = promote_synthesis(
            args.vault,
            args.synthesis,
            title=args.title,
            knowledge=args.knowledge,
            slug=args.slug,
            next_review=args.next_review,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_memory_stale(args: argparse.Namespace) -> int:
    try:
        created = mark_memory_stale(
            args.vault,
            args.note,
            reason=args.reason,
            superseded_by=args.superseded_by,
            title=args.title,
            slug=args.slug,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    if args.json:
        notes = vault.lineage(args.note)
        if not notes:
            write_json(
                {
                    "ok": False,
                    "error": f"note not found or no lineage: {args.note}",
                    "vault_path": str(vault.root),
                    "note": args.note,
                }
            )
            return 1
        write_json(
            {
                "ok": True,
                "vault_path": str(vault.root),
                "note": args.note,
                "count": len(notes),
                "notes": [note_summary(note, vault.root) for note in notes],
            }
        )
        return 0
    notes = vault.lineage(args.note)
    if not notes:
        print(f"note not found or no lineage: {args.note}", file=sys.stderr)
        return 1
    for note in notes:
        print(
            "\t".join(
                [
                    note.lifecycle_stage,
                    note.noesis_id,
                    note.rel_path.as_posix(),
                    note.status,
                    note.review_state,
                    note.title,
                ]
            )
        )
    return 0


def cmd_context_build(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    issues = vault.validate()
    if args.json:
        if issues:
            write_json(validation_error_payload(vault, issues))
            return 1
        try:
            package = compose_context(
                vault,
                scope=args.scope,
                purpose=args.purpose,
                limit=args.limit,
                max_chars=args.max_chars,
                profile=args.profile,
            )
        except ValueError as exc:
            write_json({"ok": False, "error": str(exc), "vault_path": str(vault.root)})
            return 1
        content = package.content
        output_path = None
        if args.output:
            args.output.write_text(content, encoding="utf-8")
            output_path = str(args.output)
        write_json(
            {
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
                "handoff": context_handoff_payload(package, vault.root),
                "content": content,
                "output_path": output_path,
            }
        )
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        return 1
    try:
        content = build_context(
            vault,
            scope=args.scope,
            purpose=args.purpose,
            limit=args.limit,
            max_chars=args.max_chars,
            profile=args.profile,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(content, end="")
    return 0


def cmd_context_explain(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    issues = vault.validate()
    if args.json:
        if issues:
            write_json(validation_error_payload(vault, issues))
            return 1
        try:
            package = compose_context(
                vault,
                scope=args.scope,
                purpose=args.purpose,
                limit=args.limit,
                max_chars=args.max_chars,
                profile=args.profile,
            )
        except ValueError as exc:
            write_json({"ok": False, "error": str(exc), "vault_path": str(vault.root)})
            return 1
        write_json(
            {
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
                "selection": context_package_selection_payload(package, vault.root),
                "lineage_summaries": context_lineage_summary_payloads(package, vault.root),
                "handoff": context_handoff_payload(package, vault.root),
            }
        )
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        return 1
    try:
        package = compose_context(
            vault,
            scope=args.scope,
            purpose=args.purpose,
            limit=args.limit,
            max_chars=args.max_chars,
            profile=args.profile,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(render_context_explanation(package, vault.root), end="")
    return 0


def cmd_context_write(args: argparse.Namespace) -> int:
    try:
        created = write_context_note(
            args.vault,
            scope=args.scope,
            purpose=args.purpose,
            limit=args.limit,
            max_chars=args.max_chars,
            profile=args.profile,
            title=args.title,
            slug=args.slug,
            next_review=args.next_review,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def context_package_selection_payload(package: ContextPackage, vault_root: Path) -> dict[str, Any]:
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


def context_selection_payload(selection: ContextSelection, vault_root: Path) -> dict[str, Any]:
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


def lifecycle_exclusion_summary(selections: list[ContextSelection]) -> dict[str, int]:
    summary = {"stale": 0, "superseded": 0, "archived": 0, "excluded": 0}
    for selection in selections:
        kind = context_lifecycle_exclusion_kind(selection.note)
        summary[kind] = summary.get(kind, 0) + 1
    return summary


def context_lineage_summary_payloads(package: ContextPackage, vault_root: Path) -> list[dict[str, Any]]:
    return [context_lineage_summary_payload(summary, vault_root) for summary in package.lineage_summaries]


def context_lineage_summary_payload(summary: ContextLineageSummary, vault_root: Path) -> dict[str, Any]:
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


def context_handoff_payload(package: ContextPackage, vault_root: Path) -> dict[str, Any]:
    return {
        "task_purpose": package.handoff.task_purpose,
        "assumptions": list(package.handoff.assumptions),
        "validation_commands": list(package.handoff.validation_commands),
        "next_steps": list(package.handoff.next_steps),
        "active_reviewed_knowledge": [
            note_summary(selection.note, vault_root) for selection in package.included
        ],
        "scoped_out_reviewed_knowledge": [
            context_selection_payload(selection, vault_root) for selection in package.scoped_out
        ],
        "budgeted_out_reviewed_knowledge": [
            context_selection_payload(selection, vault_root) for selection in package.budgeted_out
        ],
        "selection_provenance": {
            "included": [context_selection_payload(selection, vault_root) for selection in package.included],
            "excluded": [context_selection_payload(selection, vault_root) for selection in package.excluded],
            "scoped_out": [context_selection_payload(selection, vault_root) for selection in package.scoped_out],
            "budgeted_out": [context_selection_payload(selection, vault_root) for selection in package.budgeted_out],
        },
        "lineage_summaries": context_lineage_summary_payloads(package, vault_root),
        "lifecycle_exclusions": {
            "summary": lifecycle_exclusion_summary(package.lifecycle_excluded),
            "notes": [
                context_selection_payload(selection, vault_root)
                for selection in package.lifecycle_excluded
            ],
        },
    }


def render_context_explanation(package: ContextPackage, vault_root: Path) -> str:
    lines = ["# Noesis Context Explanation", ""]
    if package.scope:
        lines.extend([f"Scope: {package.scope}", ""])
    if package.purpose:
        lines.extend([f"Purpose: {package.purpose}", ""])
    if package.profile:
        lines.extend([f"Profile: {package.profile}", f"Profile defaults: {package.profile_description}", ""])
    if package.applied_profile_defaults:
        lines.extend([f"Applied profile defaults: {', '.join(package.applied_profile_defaults)}", ""])
    if package.limit is not None or package.max_chars is not None:
        budget = []
        if package.limit is not None:
            budget.append(f"limit {package.limit}")
        if package.max_chars is not None:
            budget.append(f"max_chars {package.max_chars}")
        lines.extend([f"Budget: {', '.join(budget)}", ""])
    lines.extend(
        [
            "Active guidance is built only from current reviewed knowledge.",
            "Lifecycle-excluded notes are background provenance only.",
            "",
            "## Summary",
            "",
            f"- Current reviewed knowledge available: {package.available_count}",
            f"- Included in active context: {len(package.included)}",
            f"- Scoped out: {len(package.scoped_out)}",
            f"- Budgeted out: {len(package.budgeted_out)}",
            f"- Lifecycle-excluded background notes: {len(package.lifecycle_excluded)}",
            "",
            "## Included Active Guidance",
            "",
        ]
    )
    if package.included:
        for selection in package.included:
            lines.append(format_selection_line(selection, vault_root))
    else:
        lines.append("No current reviewed knowledge selected.")

    lines.extend(["", "## Included Lineage Summaries", ""])
    if package.lineage_summaries:
        for summary in package.lineage_summaries:
            lines.append(format_lineage_summary(summary))
    else:
        lines.append("No included reviewed knowledge lineage to summarize.")

    lines.extend(["", "## Scoped Out", ""])
    if package.scoped_out:
        for selection in package.scoped_out:
            lines.append(format_selection_line(selection, vault_root))
    else:
        lines.append("No current reviewed knowledge was scoped out.")

    lines.extend(["", "## Budgeted Out", ""])
    if package.budgeted_out:
        for selection in package.budgeted_out:
            lines.append(format_selection_line(selection, vault_root))
    else:
        lines.append("No current reviewed knowledge was budgeted out.")

    lines.extend(["", "## Lifecycle-Excluded Background", ""])
    summary = lifecycle_exclusion_summary(package.lifecycle_excluded)
    lines.append(
        "Summary: "
        f"stale={summary['stale']}, "
        f"superseded={summary['superseded']}, "
        f"archived={summary['archived']}, "
        f"other={summary['excluded']}"
    )
    lines.append("")
    if package.lifecycle_excluded:
        for selection in package.lifecycle_excluded:
            lines.append(format_selection_line(selection, vault_root))
    else:
        lines.append("No stale, superseded, or archived reviewed memory found.")

    return "\n".join(lines).rstrip() + "\n"


def format_selection_line(selection: ContextSelection, vault_root: Path) -> str:
    try:
        rel_path = selection.note.path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = selection.note.rel_path.as_posix()
    return (
        f"- {selection.note.noesis_id} ({selection.status}, score={selection.score}, "
        f"chars={selection.content_chars}) - {selection.reason}; path: {rel_path}"
    )


def format_lineage_summary(summary: ContextLineageSummary) -> str:
    parts = [
        f"sources={format_note_ids(summary.sources)}",
        f"evidence={format_note_ids(summary.evidence)}",
        f"claims={format_note_ids(summary.claims)}",
        f"syntheses={format_note_ids(summary.syntheses)}",
        f"reviews={format_note_ids(summary.reviews)}",
    ]
    return f"- {summary.reviewed_knowledge.noesis_id}: " + "; ".join(parts)


def format_note_ids(notes: list[Any]) -> str:
    return ", ".join(note.noesis_id for note in notes) if notes else "none"


def validation_error_payload(vault: Vault, issues: list[Any]) -> dict[str, Any]:
    doctor = vault.doctor()
    return {
        "ok": False,
        "error": "vault validation failed",
        "vault_path": str(vault.root),
        "contract": doctor_payload(doctor)["contract"],
        "compatible": doctor.compatible,
        "complete": doctor.complete,
        "ready_for_cli_mcp": doctor.ready_for_cli_mcp,
        "issue_count": len(issues),
        "issues": [issue_to_dict(issue, vault.root) for issue in issues],
    }


def review_error_payload(vault: Vault, error: ValueError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(error),
        "vault_path": str(vault.root),
    }


def doctor_payload(doctor: Any) -> dict[str, Any]:
    contract_version = doctor.contract.get("contract_version")
    return {
        "ok": doctor.ready_for_cli_mcp,
        "vault_path": str(doctor.root),
        "compatible": doctor.compatible,
        "complete": doctor.complete,
        "ready_for_cli_mcp": doctor.ready_for_cli_mcp,
        "note_count": doctor.note_count,
        "contract": {
            "path": str(doctor.contract_path),
            "present": doctor.contract_path.exists(),
            "version": str(contract_version) if contract_version is not None else None,
            "supported": doctor.compatible,
            "metadata": json_safe(doctor.contract),
            "issues": [issue_to_dict(issue, doctor.root) for issue in doctor.contract_issues],
        },
        "issue_count": len(doctor.validation_issues),
        "issues": [issue_to_dict(issue, doctor.root) for issue in doctor.validation_issues],
    }


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(json_safe(payload), sort_keys=True))


def print_section_notes(title: str, sections: dict[str, list[dict[str, Any]]]) -> None:
    print(f"{title}:")
    if not sections:
        print("  none")
        return
    for key, notes in sections.items():
        print(f"  {key}:")
        for note in notes:
            print(f"    {note['noesis_id']}\t{note['path']}\t{note['review_state']}\t{note['title']}")


def print_flat_notes(title: str, notes: list[dict[str, Any]]) -> None:
    print(f"{title}:")
    if not notes:
        print("  none")
        return
    for note in notes:
        print(f"  {note['noesis_id']}\t{note['path']}\t{note['review_state']}\t{note['title']}")


def print_audit_history(audits: list[dict[str, Any]]) -> None:
    print("audit history:")
    if not audits:
        print("  none")
        return
    for audit in audits:
        print(
            "\t".join(
                [
                    "  " + str(audit.get("reviewed_at", "unknown")),
                    str(audit.get("decision", "unknown")),
                    audit["noesis_id"],
                    audit["path"],
                    audit["title"],
                ]
            )
        )
