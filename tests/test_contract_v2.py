from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import noesis.vault as vault_module

from noesis.vault import (
    Vault,
    compose_context,
    extract_wikilinks,
    file_content_hash,
    mark_memory_stale,
    migrate_vault,
    promote_synthesis,
    remove_relationship_link,
    reviewed_note_content_hash,
    renew_review,
    wikilink,
    write_context_note,
    write_note,
    write_review_decision,
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

    def test_validator_requires_source_raw_path_under_raw_directory(self) -> None:
        for via_symlink in (False, True):
            with self.subTest(via_symlink=via_symlink), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                vault = Vault.load(vault_path)
                source = vault.find_note("source-noesis-readme")
                mutable_note = vault.find_note("reviewed-knowledge-noesis-lifecycle")
                self.assertIsNotNone(source)
                self.assertIsNotNone(mutable_note)
                assert source is not None and mutable_note is not None
                raw_path = f"../knowledge/{mutable_note.path.name}"
                if via_symlink:
                    link_path = vault_path / "raw" / "mutable-knowledge-link.md"
                    link_path.symlink_to(mutable_note.path)
                    raw_path = f"../raw/{link_path.name}"
                metadata = dict(source.metadata)
                metadata["raw_path"] = raw_path
                metadata["content_hash"] = file_content_hash(mutable_note.path)
                metadata["source_size_bytes"] = mutable_note.path.stat().st_size
                write_note(source.path, metadata, source.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn("raw_path must resolve inside the vault raw directory", messages)

    def test_validator_requires_source_raw_path_to_be_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            source = vault.find_note("source-noesis-readme")
            self.assertIsNotNone(source)
            assert source is not None
            self.assertEqual(vault.validate(), [])
            metadata = dict(source.metadata)
            metadata["raw_path"] = str(
                (source.path.parent / str(source.metadata["raw_path"])).resolve()
            )
            write_note(source.path, metadata, source.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("raw_path must be vault-relative", messages)

    def test_validator_rejects_placeholder_in_mature_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            note = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(note)
            write_note(note.path, note.metadata, note.body + "\nReplace this placeholder before use.\n")

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(any("unresolved placeholder" in message for message in messages), messages)

    def test_validator_rejects_placeholder_metadata_in_mature_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            note = Vault.load(vault_path).find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(note)
            assert note is not None
            metadata = dict(note.metadata)
            metadata["title"] = "{{title}}"
            write_note(note.path, metadata, note.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn("mature note contains unresolved placeholder '{{title}}'", messages)

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

    def test_validator_requires_context_to_match_stored_selection(self) -> None:
        cases = (
            {"scope": "agent-memory"},
            {"limit": 1},
        )
        for context_options in cases:
            with self.subTest(context_options=context_options), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                created = write_context_note(
                    vault_path,
                    as_of="2026-06-13",
                    title="Selection Contract Context",
                    slug="selection-contract-context",
                    **context_options,
                )
                vault = Vault.load(vault_path)
                context = vault.find_note(created.note_id)
                self.assertIsNotNone(context)
                assert context is not None
                included_ids = {
                    note.noesis_id
                    for note in vault.current_reviewed_knowledge()
                    if wikilink(note.noesis_id) in context.metadata["reviewed_knowledge"]
                }
                extra = next(
                    note
                    for note in vault.current_reviewed_knowledge()
                    if note.noesis_id not in included_ids
                )
                metadata = dict(context.metadata)
                metadata["reviewed_knowledge"] = [
                    *metadata["reviewed_knowledge"],
                    wikilink(extra.noesis_id),
                ]
                metadata["input_hashes"] = [
                    *metadata["input_hashes"],
                    f"{extra.noesis_id}={file_content_hash(extra.path)}",
                ]
                write_note(context.path, metadata, context.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertTrue(
                    any(message.startswith("reviewed_knowledge must match stored context selection") for message in messages),
                    messages,
                )

    def test_validator_requires_default_context_to_include_all_selected_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-06-13",
                title="Default Selection Contract Context",
                slug="default-selection-contract-context",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["reviewed_knowledge"] = metadata["reviewed_knowledge"][1:]
            metadata["input_hashes"] = metadata["input_hashes"][1:]
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(
                any(message.startswith("reviewed_knowledge must match stored context selection") for message in messages),
                messages,
            )

    def test_validator_requires_ranked_context_selection_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-06-13",
                title="Ranked Selection Contract Context",
                slug="ranked-selection-contract-context",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["reviewed_knowledge"] = list(reversed(metadata["reviewed_knowledge"]))
            metadata["input_hashes"] = list(reversed(metadata["input_hashes"]))
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(
                any(message.startswith("reviewed_knowledge must match stored context selection") for message in messages),
                messages,
            )

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

    def test_validator_preserves_multiple_wikilinks_in_relationship_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-06-18",
                title="Multi-Link Selection Contract Context",
                slug="multi-link-selection-contract-context",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            expected_links = list(context.metadata["reviewed_knowledge"])
            self.assertGreater(len(expected_links), 1)
            combined = " then ".join(str(link) for link in expected_links)
            self.assertEqual(
                extract_wikilinks(combined),
                [link[2:-2] for link in expected_links],
            )
            metadata = dict(context.metadata)
            metadata["reviewed_knowledge"] = [combined]
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

    def test_validator_rejects_freshness_exclusions_eligible_under_stored_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            target_id = "reviewed-knowledge-project-memory-corpus-continuation"
            metadata = dict(context.metadata)
            metadata["freshness_excluded"] = [wikilink(target_id)]
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                f"freshness_excluded reference {wikilink(target_id)!r} is fresh as of "
                "2026-06-13 under 'balanced' freshness policy",
                messages,
            )

    def test_validator_requires_complete_freshness_exclusion_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-07-16",
                freshness_policy="strict",
                title="Strict Freshness Contract Context",
                slug="strict-freshness-contract-context",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            omitted = metadata["freshness_excluded"][0]
            metadata["freshness_excluded"] = metadata["freshness_excluded"][1:]
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(
                any(message.startswith("freshness_excluded must match stored freshness selection") for message in messages),
                (omitted, messages),
            )

    def test_validator_rejects_unknown_stored_context_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["context_profile"] = "missing-profile"
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(
                any(message.startswith("context_profile must be one of:") for message in messages),
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

    def test_validator_requires_complete_context_lifecycle_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            context = Vault.load(vault_path).find_note("context-agent-memory-dogfood")
            self.assertIsNotNone(context)
            assert context is not None
            metadata = dict(context.metadata)
            metadata["excluded_memory"] = metadata["excluded_memory"][1:]
            write_note(context.path, metadata, context.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertTrue(
                any(
                    message.startswith(
                        "excluded_memory must match the complete lifecycle exclusion set"
                    )
                    for message in messages
                ),
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

    def test_validator_requires_parseable_next_review_schedules(self) -> None:
        for value, valid in (("{{date}}", False), ("unknown", True)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                note = Vault.load(vault_path).find_note("reviewed-knowledge-noesis-lifecycle")
                self.assertIsNotNone(note)
                assert note is not None
                metadata = dict(note.metadata)
                metadata["next_review"] = value
                write_note(note.path, metadata, note.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                schedule_error = "next_review must be a parseable YYYY-MM-DD date or unknown"
                if valid:
                    self.assertNotIn(schedule_error, messages)
                else:
                    self.assertIn(schedule_error, messages)

    def test_validator_requires_latest_renewal_schedule_to_match_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            renew_review(
                vault_path,
                target_id,
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The reviewed knowledge remains current.",
                today="2026-07-16",
            )
            target = Vault.load(vault_path).find_note(target_id)
            self.assertIsNotNone(target)
            assert target is not None
            metadata = dict(target.metadata)
            metadata["next_review"] = "2026-07-13"
            write_note(target.path, metadata, target.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                f"latest renewed review audit next_review must match reviewed note {target_id!r}",
                messages,
            )

    def test_later_approval_can_replace_a_renewal_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            renew_review(
                vault_path,
                target_id,
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The reviewed knowledge remains current.",
                today="2026-07-16",
            )

            write_review_decision(
                vault_path,
                target_id,
                decision="approved",
                reviewer="test-human",
                basis="A later approval sets a new review schedule.",
                next_review="2026-09-16",
                today="2026-07-17",
            )

            vault = Vault.load(vault_path)
            target = vault.find_note(target_id)
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(str(target.metadata["next_review"]), "2026-09-16")
            self.assertEqual(vault.validate(), [])

    def test_non_covering_audit_does_not_hide_latest_renewal_schedule_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            renew_review(
                vault_path,
                target_id,
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The reviewed knowledge remains current.",
                today="2026-07-16",
            )

            vault = Vault.load(vault_path)
            target = vault.find_note(target_id)
            unrelated_audit = vault.find_note("review-local-first-lifecycle")
            self.assertIsNotNone(target)
            self.assertIsNotNone(unrelated_audit)
            assert target is not None and unrelated_audit is not None
            unrelated_metadata = dict(unrelated_audit.metadata)
            unrelated_metadata["reviewed_at"] = "2026-07-17"
            unrelated_metadata["updated"] = "2026-07-17"
            write_note(unrelated_audit.path, unrelated_metadata, unrelated_audit.body)
            target_metadata = dict(target.metadata)
            target_metadata["next_review"] = "2026-07-13"
            target_metadata["reviewed_by"] = [
                *target_metadata["reviewed_by"],
                wikilink(unrelated_audit.noesis_id),
            ]
            write_note(target.path, target_metadata, target.body)

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                f"latest renewed review audit next_review must match reviewed note {target_id!r}",
                messages,
            )

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

    def test_validator_requires_every_lineage_support_audit_to_be_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            audit = vault.find_note("review-local-first-lifecycle")
            synthesis = vault.find_note("synthesis-local-first-lifecycle-interface")
            self.assertIsNotNone(audit)
            self.assertIsNotNone(synthesis)
            assert audit is not None and synthesis is not None

            split_audit_id = "review-split-lifecycle-synthesis"
            split_audit_metadata = dict(audit.metadata)
            split_audit_metadata.update(
                {
                    "title": "Review - Split Lifecycle Synthesis",
                    "noesis_id": split_audit_id,
                    "reviewed_notes": [wikilink(synthesis.noesis_id)],
                    "aliases": [],
                }
            )
            write_note(
                vault_path / "review" / f"{split_audit_id}.md",
                split_audit_metadata,
                audit.body,
            )
            audit_metadata = dict(audit.metadata)
            audit_metadata["reviewed_notes"] = [
                link
                for link in audit_metadata["reviewed_notes"]
                if link != wikilink(synthesis.noesis_id)
            ]
            write_note(audit.path, audit_metadata, audit.body)
            synthesis_metadata = dict(synthesis.metadata)
            synthesis_metadata["reviewed_by"] = [wikilink(split_audit_id)]
            write_note(synthesis.path, synthesis_metadata, synthesis.body)

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

    def test_validator_rejects_active_knowledge_after_later_change_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            audit_path = vault_path / "review" / "review-imported-knowledge-changes.md"
            write_note(
                audit_path,
                {
                    "title": "Imported Knowledge Changes",
                    "noesis_id": "review-imported-knowledge-changes",
                    "type": "review",
                    "lifecycle_stage": "review",
                    "status": "complete",
                    "review_state": "approved",
                    "confidence": "medium",
                    "created": "2026-07-17",
                    "updated": "2026-07-17",
                    "reviewer": "imported-reviewer",
                    "reviewed_at": "2026-07-17",
                    "reviewed_notes": [wikilink(target_id)],
                    "decision": "changes-requested",
                    "tags": ["noesis", "review"],
                    "aliases": [],
                },
                """# Imported Knowledge Changes

## Decision

changes-requested

## Basis

The active knowledge requires revision.

## Changes Requested

Revise the operational guidance before reuse.
""",
            )

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "active reviewed knowledge requires an approved review audit covering it or its declared lineage",
                messages,
            )

    def test_validator_walks_nested_review_support_lineage(self) -> None:
        cases = (
            ("extracted", "ready-for-review", "non-current"),
            ("reviewed", "approved", "unaudited"),
        )
        for status, review_state, expected_state in cases:
            with self.subTest(expected_state=expected_state), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                vault = Vault.load(vault_path)
                synthesis = vault.find_note("synthesis-local-first-lifecycle-interface")
                nested = vault.find_note("evidence-cli-authoring-loop")
                self.assertIsNotNone(synthesis)
                self.assertIsNotNone(nested)
                assert synthesis is not None and nested is not None

                nested_metadata = dict(nested.metadata)
                nested_metadata["status"] = status
                nested_metadata["review_state"] = review_state
                write_note(nested.path, nested_metadata, nested.body)
                synthesis_metadata = dict(synthesis.metadata)
                synthesis_metadata["evidence"] = [
                    *synthesis_metadata["evidence"],
                    wikilink(nested.noesis_id),
                ]
                write_note(synthesis.path, synthesis_metadata, synthesis.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn(
                    f"active reviewed knowledge depends on {expected_state} evidence {nested.noesis_id!r}",
                    messages,
                )

    def test_nested_support_dependency_invalidates_knowledge_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            evidence_template = vault.find_note("evidence-memory-lifecycle")
            claim_template = vault.find_note("claim-useful-memory-requires-lifecycle")
            synthesis = vault.find_note("synthesis-local-first-lifecycle-interface")
            audit = vault.find_note("review-local-first-lifecycle")
            self.assertIsNotNone(evidence_template)
            self.assertIsNotNone(claim_template)
            self.assertIsNotNone(synthesis)
            self.assertIsNotNone(audit)
            assert evidence_template is not None
            assert claim_template is not None
            assert synthesis is not None
            assert audit is not None

            evidence_id = "evidence-nested-context-impact"
            evidence_metadata = dict(evidence_template.metadata)
            evidence_metadata.update(
                {
                    "title": "Nested Context Impact Evidence",
                    "noesis_id": evidence_id,
                    "sources": [wikilink("source-agent-memory-session")],
                    "aliases": [],
                }
            )
            write_note(
                vault_path / "evidence" / f"{evidence_id}.md",
                evidence_metadata,
                "# Nested Context Impact Evidence\n\nThis approved evidence is reachable only through a nested claim.\n",
            )

            claim_id = "claim-nested-context-impact"
            claim_metadata = dict(claim_template.metadata)
            claim_metadata.update(
                {
                    "title": "Nested Context Impact Claim",
                    "noesis_id": claim_id,
                    "sources": [wikilink("source-agent-memory-session")],
                    "evidence": [wikilink(evidence_id)],
                    "aliases": [],
                }
            )
            write_note(
                vault_path / "claims" / f"{claim_id}.md",
                claim_metadata,
                "# Nested Context Impact Claim\n\nThis approved claim connects a synthesis to nested evidence.\n",
            )

            synthesis_metadata = dict(synthesis.metadata)
            synthesis_metadata["claims"] = [*synthesis_metadata["claims"], wikilink(claim_id)]
            synthesis_metadata["sources"] = [
                *synthesis_metadata["sources"],
                wikilink("source-agent-memory-session"),
            ]
            write_note(synthesis.path, synthesis_metadata, synthesis.body)
            nested_vault = Vault.load(vault_path)
            nested_evidence = nested_vault.find_note(evidence_id)
            nested_claim = nested_vault.find_note(claim_id)
            self.assertIsNotNone(nested_evidence)
            self.assertIsNotNone(nested_claim)
            assert nested_evidence is not None and nested_claim is not None
            audit_metadata = dict(audit.metadata)
            audit_metadata["reviewed_notes"] = [
                *audit_metadata["reviewed_notes"],
                wikilink(evidence_id),
                wikilink(claim_id),
            ]
            audit_metadata["reviewed_content_hashes"] = [
                *audit_metadata["reviewed_content_hashes"],
                f"{evidence_id}={reviewed_note_content_hash(nested_evidence)}",
                f"{claim_id}={reviewed_note_content_hash(nested_claim)}",
            ]
            write_note(audit.path, audit_metadata, audit.body)

            nested_vault = Vault.load(vault_path)
            nested_evidence = nested_vault.find_note(evidence_id)
            self.assertIsNotNone(nested_evidence)
            assert nested_evidence is not None
            self.assertEqual(nested_vault.validate(), [])
            package = compose_context(
                nested_vault,
                scope="lifecycle",
                profile="codex-handoff",
                as_of="2026-06-01",
            )
            summary = next(
                item
                for item in package.lineage_summaries
                if item.reviewed_knowledge.noesis_id == "reviewed-knowledge-noesis-lifecycle"
            )
            self.assertIn(evidence_id, [note.noesis_id for note in summary.evidence])
            self.assertIn(claim_id, [note.noesis_id for note in summary.claims])
            self.assertIn(
                "source-agent-memory-session",
                [note.noesis_id for note in summary.sources],
            )
            self.assertIn(
                "context-first-cli-mcp-workflow",
                [note.noesis_id for note in nested_vault.dependent_contexts_for(nested_evidence)],
            )

            mark_memory_stale(
                vault_path,
                evidence_id,
                reason="The nested evidence is no longer current.",
                today="2026-07-16",
            )

            stale_vault = Vault.load(vault_path)
            knowledge = stale_vault.find_note("reviewed-knowledge-noesis-lifecycle")
            context = stale_vault.find_note("context-first-cli-mcp-workflow")
            self.assertIsNotNone(knowledge)
            self.assertIsNotNone(context)
            assert knowledge is not None and context is not None
            self.assertEqual(knowledge.status, "stale")
            self.assertNotIn(wikilink(knowledge.noesis_id), context.metadata["reviewed_knowledge"])
            self.assertEqual(stale_vault.validate(), [])

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

    def test_migration_rebuilds_context_selection_under_v2_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                scope="agent memory",
                as_of="2026-06-18",
                title="Legacy Ranked Selection Context",
                slug="legacy-ranked-selection-context",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            expected_links = list(context.metadata["reviewed_knowledge"])
            self.assertGreater(len(expected_links), 1)
            metadata = dict(context.metadata)
            metadata["reviewed_knowledge"] = list(reversed(expected_links))
            metadata.pop("input_hashes")
            write_note(context.path, metadata, context.body)
            self.downgrade_contract_to_v1(vault_path)

            migrate_vault(vault_path, backup=False)

            migrated_vault = Vault.load(vault_path)
            migrated_context = migrated_vault.find_note(created.note_id)
            self.assertIsNotNone(migrated_context)
            assert migrated_context is not None
            self.assertEqual(migrated_context.metadata["reviewed_knowledge"], expected_links)
            self.assertEqual(
                [str(item).split("=", maxsplit=1)[0] for item in migrated_context.metadata["input_hashes"]],
                [link[2:-2] for link in expected_links],
            )
            body_positions = [migrated_context.body.index(link) for link in expected_links]
            self.assertEqual(body_positions, sorted(body_positions))
            self.assertEqual(migrated_vault.validate(), [])

    def test_migration_repairs_nested_support_audit_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            self.downgrade_contract_to_v1(vault_path)
            vault = Vault.load(vault_path)
            original = vault.find_note("evidence-memory-lifecycle")
            claim = vault.find_note("claim-useful-memory-requires-lifecycle")
            self.assertIsNotNone(original)
            self.assertIsNotNone(claim)
            assert original is not None and claim is not None
            nested_id = "evidence-nested-migration-support"
            nested_metadata = dict(original.metadata)
            nested_metadata["title"] = "Nested Migration Support"
            nested_metadata["noesis_id"] = nested_id
            nested_metadata["reviewed_by"] = []
            nested_metadata["aliases"] = []
            write_note(
                vault_path / "evidence" / f"{nested_id}.md",
                nested_metadata,
                original.body,
            )
            claim_metadata = dict(claim.metadata)
            claim_metadata["evidence"] = [
                *claim_metadata["evidence"],
                wikilink(nested_id),
            ]
            write_note(claim.path, claim_metadata, claim.body)

            preview = migrate_vault(vault_path, dry_run=True)
            self.assertTrue(preview.dry_run)
            migrate_vault(vault_path, backup=False)

            migrated = Vault.load(vault_path)
            nested = migrated.find_note(nested_id)
            audit = migrated.find_note("review-local-first-lifecycle")
            self.assertIsNotNone(nested)
            self.assertIsNotNone(audit)
            assert nested is not None and audit is not None
            self.assertIn(wikilink(audit.noesis_id), nested.metadata["reviewed_by"])
            self.assertIn(wikilink(nested_id), audit.metadata["reviewed_notes"])
            self.assertEqual(migrated.validate(), [])

    def test_migration_hashes_the_final_rebuilt_context_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            renewed = renew_review(
                vault_path,
                "context-first-cli-mcp-workflow",
                next_review="2026-09-01",
                reviewer="migration-test",
                basis="The legacy context remains suitable for migration.",
                slug="migration-context-review",
                today="2026-07-16",
            )
            context = Vault.load(vault_path).find_note("context-first-cli-mcp-workflow")
            self.assertIsNotNone(context)
            assert context is not None
            write_note(context.path, context.metadata, f"{context.body}\nLegacy-only rendering.\n")
            self.downgrade_contract_to_v1(vault_path)

            migrate_vault(vault_path, backup=False)

            migrated = Vault.load(vault_path)
            context = migrated.find_note("context-first-cli-mcp-workflow")
            audit = migrated.find_note(renewed.note_id)
            self.assertIsNotNone(context)
            self.assertIsNotNone(audit)
            assert context is not None and audit is not None
            self.assertIn(
                f"{context.noesis_id}={reviewed_note_content_hash(context)}",
                audit.metadata["reviewed_content_hashes"],
            )
            self.assertEqual(migrated.validate(), [])

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
            vault = Vault.load(vault_path)
            for target_id in (
                "evidence-memory-lifecycle",
                "claim-useful-memory-requires-lifecycle",
                "synthesis-local-first-lifecycle-interface",
            ):
                target = vault.find_note(target_id)
                self.assertIsNotNone(target)
                assert target is not None
                target_metadata = dict(target.metadata)
                target_metadata["next_review"] = metadata["next_review"]
                write_note(target.path, target_metadata, target.body)

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

    def test_validator_requires_parseable_valid_until_dates(self) -> None:
        for invalid_value in ("{{date}}", "unknown"):
            with self.subTest(valid_until=invalid_value), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                target = Vault.load(vault_path).find_note("reviewed-knowledge-agent-memory-dogfood")
                self.assertIsNotNone(target)
                assert target is not None
                metadata = dict(target.metadata)
                metadata["valid_until"] = invalid_value
                write_note(target.path, metadata, target.body)

                messages = [issue.message for issue in Vault.load(vault_path).validate()]
                self.assertIn("valid_until must be a parseable YYYY-MM-DD date", messages)

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

    def test_renewal_preserves_other_compact_freshness_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-07-16",
                freshness_policy="strict",
                title="Compact Strict Freshness Snapshot",
            )
            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            original_links = list(context.metadata["freshness_excluded"])
            self.assertGreater(len(original_links), 1)
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            target_link = wikilink(target_id)
            self.assertIn(target_link, original_links)
            metadata = dict(context.metadata)
            metadata["freshness_excluded"] = [" and ".join(original_links)]
            write_note(context.path, metadata, context.body)
            self.assertEqual(Vault.load(vault_path).validate(), [])

            renew_review(
                vault_path,
                target_id,
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The reviewed knowledge remains current after scheduled review.",
                today="2026-07-16",
            )

            renewed_vault = Vault.load(vault_path)
            renewed_context = renewed_vault.find_note(created.note_id)
            self.assertIsNotNone(renewed_context)
            assert renewed_context is not None
            remaining_ids = {
                target
                for item in renewed_context.metadata["freshness_excluded"]
                for target in extract_wikilinks(str(item))
            }
            self.assertEqual(
                remaining_ids,
                {link[2:-2] for link in original_links if link != target_link},
            )
            self.assertEqual(renewed_vault.validate(), [])

    def test_renewal_does_not_restore_freshness_exclusion_outside_selection(self) -> None:
        cases = (
            {"scope": "corpus"},
            {"scope": "project memory corpus agent", "limit": 1},
        )
        for context_options in cases:
            with self.subTest(context_options=context_options), tempfile.TemporaryDirectory() as tmp:
                vault_path = self.copy_example(Path(tmp))
                created = write_context_note(
                    vault_path,
                    as_of="2026-07-16",
                    freshness_policy="strict",
                    title="Selection-Bounded Freshness Snapshot",
                    slug="selection-bounded-freshness",
                    **context_options,
                )
                target_id = "reviewed-knowledge-agent-memory-dogfood"
                before = Vault.load(vault_path).find_note(created.note_id)
                self.assertIsNotNone(before)
                assert before is not None
                self.assertIn(wikilink(target_id), before.metadata["freshness_excluded"])

                renew_review(
                    vault_path,
                    target_id,
                    next_review="2026-08-16",
                    reviewer="test-human",
                    basis="The reviewed knowledge remains current after scheduled review.",
                    today="2026-07-16",
                )

                renewed_vault = Vault.load(vault_path)
                context = renewed_vault.find_note(created.note_id)
                self.assertIsNotNone(context)
                assert context is not None
                self.assertNotIn(wikilink(target_id), context.metadata["reviewed_knowledge"])
                self.assertNotIn(wikilink(target_id), context.metadata["freshness_excluded"])
                self.assertEqual(renewed_vault.validate(), [])

    def test_approval_adds_newly_current_knowledge_to_existing_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            template = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(template)
            assert template is not None
            pending_id = "reviewed-knowledge-newly-approved-context-input"
            pending_metadata = dict(template.metadata)
            pending_metadata.update(
                {
                    "title": "Newly Approved Context Input",
                    "noesis_id": pending_id,
                    "status": "needs-review",
                    "review_state": "ready-for-review",
                    "updated": "2026-06-18",
                    "aliases": [],
                }
            )
            pending_metadata.pop("reviewed_at", None)
            pending_metadata.pop("next_review", None)
            pending_path = vault_path / "knowledge" / f"{pending_id}.md"
            write_note(
                pending_path,
                pending_metadata,
                template.body.replace("# Noesis Lifecycle Knowledge", "# Newly Approved Context Input", 1),
            )
            created = write_context_note(
                vault_path,
                as_of="2026-06-18",
                title="Pre-Approval Default Context",
                slug="pre-approval-default-context",
            )
            before = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(before)
            assert before is not None
            self.assertNotIn(wikilink(pending_id), before.metadata["reviewed_knowledge"])

            write_review_decision(
                vault_path,
                pending_id,
                decision="approved",
                reviewer="test-human",
                basis="The new knowledge is supported and ready for operational use.",
                today="2026-06-18",
            )

            approved_vault = Vault.load(vault_path)
            updated_context = approved_vault.find_note(created.note_id)
            self.assertIsNotNone(updated_context)
            assert updated_context is not None
            self.assertIn(wikilink(pending_id), updated_context.metadata["reviewed_knowledge"])
            self.assertEqual(approved_vault.validate(), [])

    def test_direct_promotion_adds_current_knowledge_to_existing_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                as_of="2026-06-18",
                title="Pre-Promotion Default Context",
                slug="pre-promotion-default-context",
            )

            promoted = promote_synthesis(
                vault_path,
                "synthesis-local-first-lifecycle-interface",
                title="Directly Promoted Context Input",
                slug="directly-promoted-context-input",
                today="2026-06-18",
            )

            promoted_vault = Vault.load(vault_path)
            updated_context = promoted_vault.find_note(created.note_id)
            self.assertIsNotNone(updated_context)
            assert updated_context is not None
            self.assertIn(wikilink(promoted.note_id), updated_context.metadata["reviewed_knowledge"])
            self.assertEqual(promoted_vault.validate(), [])

    def test_new_context_records_changes_requested_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-noesis-lifecycle"
            write_review_decision(
                vault_path,
                target_id,
                decision="changes-requested",
                reviewer="test-human",
                basis="The knowledge needs revision before further use.",
                changes_requested="Update the lifecycle guidance.",
                today="2026-06-18",
            )

            blocked_vault = Vault.load(vault_path)
            transient = compose_context(
                blocked_vault,
                as_of="2026-06-18",
                profile="codex-handoff",
            )
            self.assertIn(
                target_id,
                [selection.note.noesis_id for selection in transient.lifecycle_excluded],
            )
            self.assertIn(target_id, transient.content)

            created = write_context_note(
                vault_path,
                as_of="2026-06-18",
                title="Post-Change-Request Context",
                slug="post-change-request-context",
            )

            vault = Vault.load(vault_path)
            context = vault.find_note(created.note_id)
            target = vault.find_note(target_id)
            self.assertIsNotNone(context)
            self.assertIsNotNone(target)
            assert context is not None and target is not None
            self.assertIn(wikilink(target_id), context.metadata["excluded_memory"])
            self.assertIn(
                created.note_id,
                [note.noesis_id for note in vault.dependent_contexts_for(target)],
            )
            self.assertEqual(vault.validate(), [])

    def test_handoff_rewrite_refreshes_lifecycle_exclusion_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-noesis-lifecycle"
            created = write_context_note(
                vault_path,
                scope="lifecycle",
                profile="codex-handoff",
                as_of="2026-06-18",
                title="Lifecycle Rewrite Handoff",
                slug="lifecycle-rewrite-handoff",
            )

            write_review_decision(
                vault_path,
                target_id,
                decision="changes-requested",
                reviewer="test-human",
                basis="The lifecycle guidance needs revision.",
                changes_requested="Revise the lifecycle guidance.",
                today="2026-06-18",
            )
            blocked_context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(blocked_context)
            assert blocked_context is not None
            blocked_section = blocked_context.body.split("## Lifecycle Exclusions", 1)[1].split(
                "\n## ", 1
            )[0]
            self.assertIn(target_id, blocked_section)

            write_review_decision(
                vault_path,
                target_id,
                decision="approved",
                reviewer="test-human",
                basis="The revised lifecycle guidance is ready for use.",
                today="2026-06-19",
            )
            approved_vault = Vault.load(vault_path)
            approved_context = approved_vault.find_note(created.note_id)
            self.assertIsNotNone(approved_context)
            assert approved_context is not None
            approved_section = approved_context.body.split("## Lifecycle Exclusions", 1)[1].split(
                "\n## ", 1
            )[0]
            self.assertNotIn(target_id, approved_section)
            self.assertIn(wikilink(target_id), approved_context.metadata["reviewed_knowledge"])
            self.assertEqual(approved_vault.validate(), [])

    def test_handoff_rewrite_preserves_scope_and_budget_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            created = write_context_note(
                vault_path,
                scope="lifecycle",
                profile="codex-handoff",
                as_of="2026-06-18",
                title="Scoped Lifecycle Rewrite Handoff",
                slug="scoped-lifecycle-rewrite-handoff",
            )
            before = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(before)
            assert before is not None
            before_count = next(
                line
                for line in before.body.splitlines()
                if line.startswith("- Excluded by scope or budget:")
            )
            self.assertNotEqual(before_count, "- Excluded by scope or budget: 0")

            renew_review(
                vault_path,
                "reviewed-knowledge-noesis-lifecycle",
                next_review="2026-08-16",
                reviewer="test-human",
                basis="The scoped lifecycle knowledge remains current.",
                today="2026-07-16",
            )

            rewritten_vault = Vault.load(vault_path)
            rewritten = rewritten_vault.find_note(created.note_id)
            self.assertIsNotNone(rewritten)
            assert rewritten is not None
            after_count = next(
                line
                for line in rewritten.body.splitlines()
                if line.startswith("- Excluded by scope or budget:")
            )
            self.assertEqual(after_count, before_count)
            self.assertIn("(scoped_out,", rewritten.body)
            self.assertEqual(rewritten_vault.validate(), [])

    def test_approval_does_not_restore_review_exclusion_outside_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            created = write_context_note(
                vault_path,
                scope="corpus",
                as_of="2026-07-16",
                title="Selection-Bounded Review Snapshot",
            )
            write_review_decision(
                vault_path,
                target_id,
                decision="changes-requested",
                reviewer="test-human",
                basis="The knowledge needs another review.",
                changes_requested="Reconfirm the operational guidance.",
                today="2026-07-16",
            )

            context = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            context_metadata = dict(context.metadata)
            context_metadata["excluded_memory"] = [
                *context_metadata["excluded_memory"],
                wikilink(target_id),
            ]
            write_note(context.path, context_metadata, context.body)
            self.assertEqual(Vault.load(vault_path).validate(), [])

            write_review_decision(
                vault_path,
                target_id,
                decision="approved",
                reviewer="test-human",
                basis="The operational guidance has been reconfirmed.",
                today="2026-07-17",
            )

            approved_vault = Vault.load(vault_path)
            updated_context = approved_vault.find_note(created.note_id)
            self.assertIsNotNone(updated_context)
            assert updated_context is not None
            self.assertNotIn(wikilink(target_id), updated_context.metadata["reviewed_knowledge"])
            self.assertNotIn(wikilink(target_id), updated_context.metadata["excluded_memory"])
            self.assertEqual(approved_vault.validate(), [])

    def test_mark_stale_rewrites_freshness_only_context_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target_id = "reviewed-knowledge-agent-memory-dogfood"
            created = write_context_note(
                vault_path,
                scope="agent memory",
                as_of="2026-07-16",
                freshness_policy="strict",
                title="Freshness-Only Stale Snapshot",
            )
            before = Vault.load(vault_path).find_note(created.note_id)
            self.assertIsNotNone(before)
            assert before is not None
            self.assertIn(wikilink(target_id), before.metadata["freshness_excluded"])
            self.assertNotIn(wikilink(target_id), before.metadata["reviewed_knowledge"])

            stale = mark_memory_stale(
                vault_path,
                target_id,
                reason="The reviewed knowledge is no longer current.",
                today="2026-07-16",
            )

            stale_vault = Vault.load(vault_path)
            context = stale_vault.find_note(created.note_id)
            self.assertIsNotNone(context)
            assert context is not None
            self.assertNotIn(wikilink(target_id), context.metadata["freshness_excluded"])
            self.assertIn(wikilink(target_id), context.metadata["excluded_memory"])
            self.assertIn(wikilink(stale.note_id), context.metadata["excluded_memory"])
            self.assertEqual(stale_vault.validate(), [])

    def test_mark_stale_records_all_lifecycle_exclusions_in_every_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            original = vault.find_note("reviewed-knowledge-noesis-lifecycle")
            self.assertIsNotNone(original)
            assert original is not None
            duplicate_id = "reviewed-knowledge-unselected-lifecycle"
            duplicate_metadata = dict(original.metadata)
            duplicate_metadata["title"] = "Unselected Lifecycle Knowledge"
            duplicate_metadata["noesis_id"] = duplicate_id
            duplicate_metadata["aliases"] = []
            write_note(
                vault_path / "knowledge" / f"{duplicate_id}.md",
                duplicate_metadata,
                original.body,
            )
            self.assertEqual(Vault.load(vault_path).validate(), [])

            mark_memory_stale(
                vault_path,
                "source-noesis-readme",
                reason="The source is no longer current.",
                today="2026-07-16",
            )

            stale_vault = Vault.load(vault_path)
            context = stale_vault.find_note("context-first-cli-mcp-workflow")
            self.assertIsNotNone(context)
            assert context is not None
            self.assertIn(wikilink(original.noesis_id), context.metadata["excluded_memory"])
            self.assertIn(wikilink(duplicate_id), context.metadata["excluded_memory"])
            self.assertEqual(stale_vault.validate(), [])

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

    def test_review_approval_is_invalidated_by_same_date_content_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            target = Vault.load(vault_path).find_note("synthesis-local-first-lifecycle-interface")
            self.assertIsNotNone(target)
            assert target is not None

            write_note(target.path, target.metadata, f"{target.body}\nUnreviewed same-date edit.\n")

            messages = [issue.message for issue in Vault.load(vault_path).validate()]
            self.assertIn(
                "review audit content hash must match reviewed note "
                "'synthesis-local-first-lifecycle-interface'",
                messages,
            )

    def test_multi_note_write_rolls_back_after_write_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            vault = Vault.load(vault_path)
            first = vault.find_note("evidence-memory-lifecycle")
            second = vault.find_note("claim-useful-memory-requires-lifecycle")
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            assert first is not None and second is not None
            original_text = {
                first.path: first.path.read_text(encoding="utf-8"),
                second.path: second.path.read_text(encoding="utf-8"),
            }
            original_write_note = vault_module.write_note
            call_count = 0

            def fail_second_write(path: Path, metadata: dict[str, object], body: str) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated write failure")
                original_write_note(path, metadata, body)

            writes = [
                (first.path, first.metadata, f"{first.body}\nChanged first.\n"),
                (second.path, second.metadata, f"{second.body}\nChanged second.\n"),
            ]
            with patch("noesis.vault.write_note", side_effect=fail_second_write):
                with self.assertRaisesRegex(OSError, "simulated write failure"):
                    vault_module.write_notes_and_validate(vault_path, writes)

            for path, text in original_text.items():
                self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_removing_relationship_link_preserves_annotations(self) -> None:
        vault = Vault.load(EXAMPLE_VAULT)
        metadata = {
            "claims": [
                "[[claim-useful-memory-requires-lifecycle]] then "
                "[[claim-agent-memory-dogfood]] # selected"
            ]
        }

        remove_relationship_link(
            vault,
            metadata,
            "claims",
            "claim-useful-memory-requires-lifecycle",
        )

        self.assertEqual(metadata["claims"], ["then [[claim-agent-memory-dogfood]] # selected"])
