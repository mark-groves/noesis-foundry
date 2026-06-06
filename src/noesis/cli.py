from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .vault import Vault, build_context, extract_evidence, ingest_source, init_vault, propose_claim


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

    review = subcommands.add_parser("review", help="Review workflows")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    queue = review_commands.add_parser("queue", help="List notes that need review")
    queue.add_argument("--vault", type=Path, required=True)
    queue.set_defaults(func=cmd_review_queue)

    trace = subcommands.add_parser("trace", help="Trace one note's lineage")
    trace.add_argument("note", help="noesis_id, filename stem, or wikilink")
    trace.add_argument("--vault", type=Path, required=True)
    trace.set_defaults(func=cmd_trace)

    context = subcommands.add_parser("context", help="Operational context workflows")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    build = context_commands.add_parser("build", help="Build context from reviewed knowledge")
    build.add_argument("--vault", type=Path, required=True)
    build.add_argument("--scope", default=None)
    build.add_argument("--purpose", default=None)
    build.add_argument("--output", type=Path, default=None)
    build.set_defaults(func=cmd_context_build)

    return parser


def cmd_vault_init(args: argparse.Namespace) -> int:
    created = init_vault(args.path, force=args.force)
    print(f"initialized {Path(args.path).resolve()}")
    print(f"created_or_checked {len(created)} paths")
    return 0


def cmd_vault_validate(args: argparse.Namespace) -> int:
    vault = Vault.load(args.path)
    issues = vault.validate()
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


def cmd_review_queue(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
    issues = vault.validate()
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


def cmd_trace(args: argparse.Namespace) -> int:
    vault = Vault.load(args.vault)
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
