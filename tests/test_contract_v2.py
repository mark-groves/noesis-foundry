from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from noesis.vault import Vault, compose_context, migrate_vault, write_context_note, write_note


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


class ContractV2Tests(unittest.TestCase):
    def copy_example(self, root: Path) -> Path:
        vault_path = root / "vault"
        shutil.copytree(EXAMPLE_VAULT, vault_path)
        return vault_path

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

    def test_migration_has_dry_run_backup_and_validated_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = self.copy_example(Path(tmp))
            contract_path = vault_path / "noesis.vault.yaml"
            contract_text = contract_path.read_text(encoding="utf-8")
            contract_path.write_text(
                contract_text.replace('contract_version: "2"', 'contract_version: "1"').replace(
                    'requires_noesis: ">=0.2.0"', 'requires_noesis: ">=0.1.0"'
                ),
                encoding="utf-8",
            )
            source = Vault.load(vault_path).find_note("source-noesis-readme")
            self.assertIsNotNone(source)
            metadata = dict(source.metadata)
            metadata.pop("content_hash", None)
            metadata.pop("content_hash_algorithm", None)
            metadata.pop("source_size_bytes", None)
            write_note(source.path, metadata, source.body)

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
            expired = compose_context(Vault.load(vault_path), scope="agent memory", as_of="2026-07-16")
            excluded = next(item for item in expired.freshness_excluded if item.note.noesis_id == target.noesis_id)
            self.assertEqual(excluded.freshness_state, "expired")

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
