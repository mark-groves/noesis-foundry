from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .mcp_server import issue_to_dict, json_safe, note_summary
from .vault import (
    Vault,
    approve_review,
    build_context,
    extract_evidence,
    filter_knowledge_by_scope,
    ingest_source,
    init_vault,
    mark_memory_stale,
    promote_synthesis,
    propose_claim,
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

    ingest = subcommands.add_parser("ingest", help="Ingest source material")
    ingest_commands = ingest.add_subparsers(dest="ingest_command", required=True)
    source = ingest_commands.add_parser("source", help="Copy a raw source and create a source note")
    source.add_argument("--vault", type=Path, required=True)
    source.add_argument("--file", type=Path, required=True)
    source.add_argument("--title", required=True)
    source.add_argument("--slug", default=None)
    source.add_argument("--source-type", default="file")
    source.add_argument("--original-url", default="unknown")
    source.add_argument("--author", default="unknown")
    source.add_argument("--source-date", default="unknown")
    source.set_defaults(func=cmd_ingest_source)

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
    queue.add_argument("--json", action="store_true", help="Write structured JSON")
    queue.set_defaults(func=cmd_review_queue)

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
    build.add_argument("--output", type=Path, default=None)
    build.add_argument("--json", action="store_true", help="Write structured JSON")
    build.set_defaults(func=cmd_context_build)

    write = context_commands.add_parser("write", help="Write an operational context note")
    write.add_argument("--vault", type=Path, required=True)
    write.add_argument("--scope", default=None)
    write.add_argument("--purpose", default=None)
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
    if args.json:
        write_json(
            {
                "ok": not issues,
                "vault_path": str(vault.root),
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
    print(f"notes: {len(vault.notes)}")
    return 0


def cmd_ingest_source(args: argparse.Namespace) -> int:
    try:
        created = ingest_source(
            args.vault,
            args.file,
            args.title,
            slug=args.slug,
            source_type=args.source_type,
            original_url=args.original_url,
            author=args.author,
            source_date=args.source_date,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


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
    if args.json:
        if issues:
            write_json(validation_error_payload(vault, issues))
            return 1
        queue = vault.review_queue()
        write_json(
            {
                "ok": True,
                "vault_path": str(vault.root),
                "count": len(queue),
                "notes": [note_summary(note, vault.root) for note in queue],
            }
        )
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        print(f"validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1
    queue = vault.review_queue()
    if not queue:
        print("review queue empty")
        return 0
    for note in queue:
        next_review = note.metadata.get("next_review", "")
        print(
            "\t".join(
                [
                    note.noesis_id,
                    note.rel_path.as_posix(),
                    note.review_state,
                    note.status,
                    str(next_review),
                    note.title,
                ]
            )
        )
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
        content = build_context(vault, scope=args.scope, purpose=args.purpose)
        output_path = None
        if args.output:
            args.output.write_text(content, encoding="utf-8")
            output_path = str(args.output)
        knowledge = filter_knowledge_by_scope(vault.current_reviewed_knowledge(), args.scope)
        write_json(
            {
                "ok": True,
                "vault_path": str(vault.root),
                "scope": args.scope,
                "purpose": args.purpose,
                "reviewed_knowledge_count": len(knowledge),
                "reviewed_knowledge": [note_summary(note, vault.root) for note in knowledge],
                "content": content,
                "output_path": output_path,
            }
        )
        return 0
    if issues:
        for issue in issues:
            print(f"ERROR {issue.format(vault.root)}", file=sys.stderr)
        return 1
    content = build_context(vault, scope=args.scope, purpose=args.purpose)
    if args.output:
        args.output.write_text(content, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(content, end="")
    return 0


def cmd_context_write(args: argparse.Namespace) -> int:
    try:
        created = write_context_note(
            args.vault,
            scope=args.scope,
            purpose=args.purpose,
            title=args.title,
            slug=args.slug,
            next_review=args.next_review,
        )
    except ValueError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(f"created {created.note_id}\t{created.path}")
    return 0


def validation_error_payload(vault: Vault, issues: list[Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "vault validation failed",
        "vault_path": str(vault.root),
        "issue_count": len(issues),
        "issues": [issue_to_dict(issue, vault.root) for issue in issues],
    }


def write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(json_safe(payload), sort_keys=True))
