from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from noesis.vault import (
    Vault,
    compose_context,
    file_content_hash,
    migrate_vault,
    renew_review,
    write_context_note,
    write_note,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


class ContractV2Tests(unittest.TestCase):
    def copy_example(self, root: Path) -> Path:
        vault_path = root / "vault"
        shutil.copytree(EXAMPLE_VAULT, vault_path)
        return vault_path

    def downgrade_contract_to_v1(self, vault_path: Path) -> None:
        contract_path = vault_path / "noesis.vault.yaml"
        contract_text = contract_path.read_text(encoding="utf-8")
        contract_path.write_text(
            contract_text.replace('contract_version: "2"', 'contract_version: "1"').replace(
                'requires_noesis: ">=0.2.0"', 'requires_noesis: ">=0.1.0"'
            ),
            encoding="utf-8",
        )

    def test_validator_detects_raw_source_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            raw_path = vault_path / "raw" / "2026-05-29-noesis-readme-excerpt.md"
            raw_path.write_text(raw_path.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(any("content hash mismatch" in message for message in messages), messages)
            self.assertTrue(any("source size mismatch" in message for message in messages), messages)

    def test_validator_rejects_placeholder_in_mature_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            note = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(note)
            write_note(note.path, note.metadata, note.body + "\nReplace this placeholder before use.\n")

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(any("unresolved placeholder" in message for message in messages), messages)

    def test_validator_requires_operational_context_input_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            context = vault.find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata.pop("input_hashes")
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("operational context requires input_hashes", messages)

    def test_validator_rejects_incorrect_context_input_hash_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            note_id = str(metadata["input_hashes"][0]).split("=", maxsplit=1)[0]
            metadata["input_hashes"] = [f"{note_id}=sha256:{'0' * 64}"]
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                f"input_hashes digest for reviewed knowledge {note_id!r} does not match its file content",
                messages,
            )

    def test_validator_parses_annotated_context_relationship_wikilinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["reviewed_knowledge"] = [f"{metadata['reviewed_knowledge'][0]} # selected"]
            write_note(context.path, metadata, context.body)

            self.assertEqual(Vault.load(vault_path).validate(), [])

    def test_validator_rejects_active_and_freshness_excluded_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["freshness_excluded"] = list(metadata["reviewed_knowledge"])
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "reviewed_knowledge and freshness_excluded must not overlap: "
                "reviewed-knowledge-agent-memory-dogfood",
                messages,
            )

    def test_validator_requires_explicit_context_freshness_metadata(self) -> None:
        required_fields = {
            "as_of": "operational context requires as_of",
            "freshness_policy": "operational context requires freshness_policy",
        }
        for field, expected in required_fields.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
                self.assertIsNotNone(context)
                assert context is not None
                metadata = dict(context.metadata)
                metadata.pop(field)
                if field == "as_of":
                    metadata["created"] = "unknown"
                write_note(context.path, metadata, context.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn(expected, messages)

    def test_validator_requires_change_request_state_for_context_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            context = vault.find_note("context-agent-memory-dogfood")
            pending = vault.find_note("evidence-cli-authoring-loop")
            self.assertIsNotNone(context)
            self.assertIsNotNone(pending)
            assert context is not None and pending is not None

            pending_metadata = dict(pending.metadata)
            pending_metadata["status"] = "needs-review"
            pending_metadata["review_state"] = "ready-for-review"
            write_note(pending.path, pending_metadata, pending.body)
            context_metadata = dict(context.metadata)
            context_metadata["excluded_memory"] = [f"[[{pending.noesis_id}]]"]
            write_note(context.path, context_metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "excluded_memory reference '[[evidence-cli-authoring-loop]]' is not stale, "
                "superseded, archived, or changes-requested",
                messages,
            )

    def test_validator_requires_every_review_note_to_record_a_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["title"] = "Decisionless Review Audit"
            metadata["noesis_id"] = "review-decisionless"
            metadata.pop("decision")
            write_note(vault_path / "review" / "review-decisionless.md", metadata, audit.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("review audit requires a decision", messages)

    def test_validator_requires_scalar_reviewer_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["reviewer"] = ["test-human"]
            write_note(audit.path, metadata, audit.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("review audit requires an identified reviewer", messages)

    def test_validator_requires_completed_approval_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["status"] = "draft"
            metadata["review_state"] = "in-review"
            write_note(audit.path, metadata, audit.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "review decision audit must have complete status and a mature review_state",
                messages,
            )
            self.assertIn(
                "active reviewed knowledge requires an approved review audit covering it or its declared lineage",
                messages,
            )

    def test_validator_requires_reviewed_at_on_completed_audit(self) -> None:
        for reviewed_at in (None, "unknown", "{{date}}"):
            with self.subTest(reviewed_at=reviewed_at), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
                self.assertIsNotNone(audit)
                assert audit is not None
                metadata = dict(audit.metadata)
                if reviewed_at is None:
                    metadata.pop("reviewed_at")
                else:
                    metadata["reviewed_at"] = reviewed_at
                write_note(audit.path, metadata, audit.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn("review decision audit requires a parseable reviewed_at date", messages)

    def test_validator_requires_completed_changes_requested_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["title"] = "Draft Changes Requested Audit"
            metadata["noesis_id"] = "review-draft-changes-requested"
            metadata["status"] = "draft"
            metadata["review_state"] = "in-review"
            metadata["decision"] = "changes-requested"
            body = audit.body.replace(
                "## Changes Requested\n\nNone.",
                "## Changes Requested\n\nRevise the evidence.",
            )
            write_note(vault_path / "review" / "review-draft-changes-requested.md", metadata, body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "review decision audit must have complete status and a mature review_state",
                messages,
            )

    def test_validator_requires_renewed_review_to_record_next_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            audit = Vault.load(vault_path).find_note("review-agent-memory-dogfood")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["decision"] = "renewed"
            metadata.pop("next_review", None)
            write_note(audit.path, metadata, audit.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("renewed review audit requires next_review", messages)

    def test_validator_requires_review_audit_to_cover_knowledge_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            knowledge = Vault.load(vault_path).find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(knowledge)
            assert knowledge is not None
            metadata = dict(knowledge.metadata)
            metadata["reviewed_by"] = ["[[review-agent-memory-dogfood]]"]
            write_note(knowledge.path, metadata, knowledge.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "active reviewed knowledge requires an approved review audit covering it or its declared lineage",
                messages,
            )

    def test_validator_rejects_approval_audits_older_than_reviewed_edits(self) -> None:
        cases = (
            (
                "reviewed-knowledge-noesis-lifecycle",
                "active reviewed knowledge requires an approved review audit covering it or its declared lineage",
            ),
            (
                "evidence-memory-lifecycle",
                "active reviewed knowledge depends on unaudited evidence 'evidence-memory-lifecycle'",
            ),
        )
        for note_id, expected in cases:
            with self.subTest(note_id=note_id), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                target = Vault.load(vault_path).find_note(note_id)
                self.assertIsNotNone(target)
                assert target is not None
                metadata = dict(target.metadata)
                metadata["updated"] = "2026-05-30"
                write_note(target.path, metadata, target.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn(expected, messages)

    def test_validator_requires_requested_change_audit_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            audit = vault.find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["title"] = "Incomplete Changes Requested Audit"
            metadata["noesis_id"] = "review-incomplete-changes-requested"
            metadata["decision"] = "changes-requested"
            body = """# Incomplete Changes Requested Audit

## Decision

changes-requested

## Basis

The review found a problem that needs correction.

## Changes Requested

## Next Review

Not scheduled.
"""
            write_note(vault_path / "review" / "review-incomplete-changes-requested.md", metadata, body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("changes-requested review audit requires requested-change details", messages)

    def test_invalid_active_lineage_cannot_reach_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            evidence = vault.find_note("evidence-memory-lifecycle")
            self.assertIsNotNone(evidence)
            metadata = dict(evidence.metadata)
            metadata["status"] = "extracted"
            metadata["review_state"] = "ready-for-review"
            write_note(evidence.path, metadata, evidence.body)

            invalid = Vault.load(vault_path)
            with self.assertRaisesRegex(ValueError, "cannot build context from invalid vault"):
                compose_context(invalid, scope="lifecycle", as_of="2026-06-01")

    def test_validator_rejects_active_knowledge_with_excluded_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            source = vault.find_note("source-agent-memory-session")
            self.assertIsNotNone(source)
            assert source is not None
            metadata = dict(source.metadata)
            metadata["status"] = "stale"
            write_note(source.path, metadata, source.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "active reviewed knowledge depends on non-current source 'source-agent-memory-session'",
                messages,
            )

    def test_validator_rejects_active_knowledge_with_excluded_support_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            knowledge = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            evidence = vault.find_note("evidence-memory-lifecycle")
            support_source = vault.find_note("source-agent-memory-session")
            self.assertIsNotNone(knowledge)
            self.assertIsNotNone(evidence)
            self.assertIsNotNone(support_source)
            assert knowledge is not None and evidence is not None and support_source is not None

            evidence_metadata = dict(evidence.metadata)
            evidence_metadata["sources"] = [f"[[{support_source.noesis_id}]]"]
            write_note(evidence.path, evidence_metadata, evidence.body)
            source_metadata = dict(support_source.metadata)
            source_metadata["status"] = "stale"
            write_note(support_source.path, source_metadata, support_source.body)

            issues = Vault.load(vault_path).validate()
            self.assertTrue(
                any(
                    issue.path == knowledge.path
                    and issue.message
                    == "active reviewed knowledge depends on non-current source "
                    "'source-agent-memory-session'"
                    for issue in issues
                ),
                [issue.message for issue in issues],
            )

    def test_validator_rejects_active_knowledge_with_unaudited_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            knowledge = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            evidence = vault.find_note("evidence-memory-lifecycle")
            audit = vault.find_note("review-local-first-lifecycle")
            self.assertIsNotNone(knowledge)
            self.assertIsNotNone(evidence)
            self.assertIsNotNone(audit)
            assert knowledge is not None and evidence is not None and audit is not None

            evidence_metadata = dict(evidence.metadata)
            evidence_metadata["reviewed_by"] = []
            write_note(evidence.path, evidence_metadata, evidence.body)
            audit_metadata = dict(audit.metadata)
            audit_metadata["reviewed_notes"] = [
                link
                for link in audit_metadata["reviewed_notes"]
                if evidence.noesis_id not in str(link)
            ]
            write_note(audit.path, audit_metadata, audit.body)

            issues = Vault.load(vault_path).validate()
            self.assertTrue(
                any(
                    issue.path == knowledge.path
                    and issue.message
                    == "active reviewed knowledge depends on unaudited evidence "
                    "'evidence-memory-lifecycle'"
                    for issue in issues
                ),
                [issue.message for issue in issues],
            )

    def test_migration_has_dry_run_backup_and_validated_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            contract_path = vault_path / "noesis.vault.yaml"
            self.downgrade_contract_to_v1(vault_path)
            source = Vault.load(vault_path).find_note("source-noesis-readme")
            self.assertIsNotNone(source)
            metadata = dict(source.metadata)
            metadata.pop("content_hash", None)
            metadata.pop("content_hash_algorithm", None)
            metadata.pop("source_size_bytes", None)
            write_note(source.path, metadata, source.body)

            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            context_metadata = dict(context.metadata)
            context_metadata.pop("as_of")
            context_metadata["created"] = "unknown"
            write_note(context.path, context_metadata, context.body)

            (vault_path / ".noesis.lock").unlink(missing_ok=True)
            before_preview = {
                path.relative_to(vault_path): path.read_bytes()
                for path in vault_path.rglob("*")
                if path.is_file()
            }
            preview = migrate_vault(vault_path, dry_run=True)
            self.assertTrue(preview.dry_run)
            self.assertGreater(len(preview.changed_paths), 1)
            self.assertIn('contract_version: "1"', contract_path.read_text(encoding="utf-8"))
            after_preview = {
                path.relative_to(vault_path): path.read_bytes()
                for path in vault_path.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after_preview, before_preview)

            migrated = migrate_vault(vault_path)
            self.assertFalse(migrated.dry_run)
            self.assertIsNotNone(migrated.backup_path)
            self.assertTrue(migrated.backup_path.is_dir())
            self.assertEqual(Vault.load(vault_path).validate(), [])
            migrated_source = Vault.load(vault_path).find_note("source-noesis-readme")
            self.assertTrue(str(migrated_source.metadata["content_hash"]).startswith("sha256:"))
            migrated_context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertRegex(str(migrated_context.metadata["as_of"]), r"^\d{4}-\d{2}-\d{2}$")

    def test_migration_rejects_excluded_or_blocked_active_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            evidence = Vault.load(vault_path).find_note("evidence-memory-lifecycle")
            self.assertIsNotNone(evidence)
            assert evidence is not None
            metadata = dict(evidence.metadata)
            metadata["status"] = "stale"
            write_note(evidence.path, metadata, evidence.body)

            with self.assertRaisesRegex(
                ValueError,
                "cannot migrate active knowledge with excluded, blocked, or unreviewed evidence: "
                "evidence-memory-lifecycle",
            ):
                migrate_vault(vault_path, dry_run=True)

    def test_migration_rejects_pending_active_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            evidence = Vault.load(vault_path).find_note("evidence-memory-lifecycle")
            self.assertIsNotNone(evidence)
            assert evidence is not None
            metadata = dict(evidence.metadata)
            metadata["status"] = "extracted"
            metadata["review_state"] = "ready-for-review"
            write_note(evidence.path, metadata, evidence.body)

            with self.assertRaisesRegex(
                ValueError,
                "cannot migrate active knowledge with excluded, blocked, or unreviewed evidence: "
                "evidence-memory-lifecycle",
            ):
                migrate_vault(vault_path, dry_run=True)

    def test_migration_rejects_excluded_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            source = Vault.load(vault_path).find_note("source-noesis-readme")
            self.assertIsNotNone(source)
            assert source is not None
            metadata = dict(source.metadata)
            metadata["status"] = "stale"
            write_note(source.path, metadata, source.body)

            with self.assertRaisesRegex(
                ValueError,
                "cannot migrate active knowledge with excluded source: source-noesis-readme",
            ):
                migrate_vault(vault_path, dry_run=True)

    def test_migration_rejects_unrelated_approved_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            knowledge = Vault.load(vault_path).find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(knowledge)
            assert knowledge is not None
            metadata = dict(knowledge.metadata)
            metadata["reviewed_by"] = ["[[review-agent-memory-dogfood]]"]
            write_note(knowledge.path, metadata, knowledge.body)

            with self.assertRaisesRegex(
                ValueError,
                "cannot migrate active knowledge without an approved audit covering it or its declared lineage: "
                "reviewed-knowledge-noesis-lifecycle",
            ):
                migrate_vault(vault_path, dry_run=True)

    def test_migration_dry_run_validates_vault_level_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            shutil.rmtree(vault_path / "_canvas")

            with self.assertRaisesRegex(
                ValueError,
                "cannot migrate invalid projected vault: _canvas: required vault folder is missing",
            ):
                migrate_vault(vault_path, dry_run=True)

    def test_migration_accepts_covering_renewed_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            audit = Vault.load(vault_path).find_note("review-local-first-lifecycle")
            self.assertIsNotNone(audit)
            assert audit is not None
            metadata = dict(audit.metadata)
            metadata["decision"] = "renewed"
            write_note(audit.path, metadata, audit.body)

            preview = migrate_vault(vault_path, dry_run=True)
            self.assertTrue(preview.dry_run)

    def test_context_freshness_distinguishes_review_due_from_expired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            target = vault.find_note("reviewed-knowledge-agent-memory-dogfood")
            self.assertIsNotNone(target)

            balanced = compose_context(vault, scope="agent memory", as_of="2026-07-16")
            self.assertIn(target.noesis_id, [note.noesis_id for note in balanced.reviewed_knowledge])
            included = next(item for item in balanced.included if item.note.noesis_id == target.noesis_id)
            self.assertEqual(included.freshness_state, "review-due")

            strict = compose_context(
                vault,
                scope="agent memory",
                as_of="2026-07-16",
                freshness_policy="strict",
            )
            self.assertNotIn(target.noesis_id, [note.noesis_id for note in strict.reviewed_knowledge])
            self.assertIn(target.noesis_id, [item.note.noesis_id for item in strict.freshness_excluded])

            metadata = dict(target.metadata)
            metadata["valid_until"] = "2026-07-15"
            write_note(target.path, metadata, target.body)
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            context_metadata = dict(context.metadata)
            context_metadata["input_hashes"] = [f"{target.noesis_id}={file_content_hash(target.path)}"]
            write_note(context.path, context_metadata, context.body)
            expired = compose_context(Vault.load(vault_path), scope="agent memory", as_of="2026-07-16")
            excluded = next(item for item in expired.freshness_excluded if item.note.noesis_id == target.noesis_id)
            self.assertEqual(excluded.freshness_state, "expired")

    def test_context_freshness_provenance_is_not_double_counted(self) -> None:
        vault = Vault.load(EXAMPLE_VAULT)
        package = compose_context(
            vault,
            as_of="2026-07-16",
            freshness_policy="strict",
            profile="agent-handoff",
        )

        self.assertIn("- Excluded by scope or budget: 0", package.content)
        self.assertIn("- Excluded by freshness: 3", package.content)
        for selection in package.freshness_excluded:
            self.assertEqual(
                package.content.count(f"- {selection.note.noesis_id} (freshness_excluded"),
                1,
            )

    def test_renewal_preserves_historical_freshness_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-07-16",
                freshness_policy="strict",
                title="Strict Freshness Snapshot",
            )
            context_note = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context_note)
            assert context_note is not None
            self.assertIn(
                "[[reviewed-knowledge-agent-memory-dogfood]]",
                context_note.metadata["freshness_excluded"],
            )
            vault = Vault.load(vault_path)
            target = vault.find_note("reviewed-knowledge-agent-memory-dogfood")
            self.assertIsNotNone(target)
            assert target is not None
            dependent_context_ids = {
                note.noesis_id
                for note in vault.dependent_contexts_for(target)
            }
            self.assertIn(created.note_id, dependent_context_ids)

            renew_review(
                vault_path,
                "reviewed-knowledge-agent-memory-dogfood",
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The reviewed knowledge remains current after scheduled review.",
                today="2026-07-16",
            )

            renewed_vault = Vault.load(vault_path)
            renewed_context = renewed_vault.find_note(created.note_id)
            self.assertIsNotNone(renewed_context)
            assert renewed_context is not None
            self.assertIn(
                "[[reviewed-knowledge-agent-memory-dogfood]]",
                renewed_context.metadata["reviewed_knowledge"],
            )
            self.assertNotIn(
                "[[reviewed-knowledge-agent-memory-dogfood]]",
                renewed_context.metadata["freshness_excluded"],
            )
            self.assertEqual(renewed_vault.validate(), [])

    def test_renewal_updates_selected_context_input_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            handoff = write_context_note(
                vault_path,
                scope="lifecycle",
                profile="codex-handoff",
                as_of="2026-06-01",
                title="Renewed Lifecycle Handoff",
                slug="renewed-lifecycle-handoff",
            )
            renew_review(
                vault_path,
                "reviewed-knowledge-noesis-lifecycle",
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The lifecycle knowledge remains current after scheduled review.",
                today="2026-07-16",
                slug="lifecycle-renewed-handoff",
            )

            vault = Vault.load(vault_path)
            knowledge = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            context = vault.find_note("context-first-cli-mcp-workflow")
            self.assertIsNotNone(knowledge)
            self.assertIsNotNone(context)
            assert knowledge is not None and context is not None
            self.assertEqual(
                context.metadata["input_hashes"],
                [f"{knowledge.noesis_id}={file_content_hash(knowledge.path)}"],
            )
            handoff_context = vault.find_note(handoff.note_id)
            self.assertIsNotNone(handoff_context)
            assert handoff_context is not None
            self.assertIn("review-lifecycle-renewed-handoff", handoff_context.body)
            self.assertEqual(vault.validate(), [])

    def test_written_context_records_reproducible_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                scope="project memory corpus",
                as_of="2026-07-16",
                freshness_policy="strict",
                title="Reproducible Context",
            )
            note = Vault.load(vault_path).find_note(created.note_id)
            self.assertEqual(str(note.metadata["as_of"]), "2026-07-16")
            self.assertEqual(note.metadata["freshness_policy"], "strict")
            self.assertTrue(note.metadata["input_hashes"])
            self.assertTrue(all("=sha256:" in value for value in note.metadata["input_hashes"]))
            self.assertEqual(Vault.load(vault_path).validate(), [])
