from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from noesis.vault import Vault


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


def run_noesis(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "noesis", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class NoesisCliTests(unittest.TestCase):
    def test_example_vault_validates(self) -> None:
        result = run_noesis("vault", "validate", str(EXAMPLE_VAULT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation ok", result.stdout)
        self.assertIn("notes:", result.stdout)

    def test_initialized_vault_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertTrue((vault_path / "_bases" / "review-queue.base").exists())
            self.assertTrue((vault_path / "_canvas" / "noesis-lifecycle.canvas").exists())
            self.assertTrue((vault_path / "_templates" / "source.md").exists())

            evidence_template = (vault_path / "_templates" / "evidence.md").read_text(encoding="utf-8")
            self.assertIn('  - "[[<source-note>]]"', evidence_template)

    def test_authoring_loop_creates_reviewable_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "research-note.md"
            raw_source.write_text(
                "# Research Note\n\nMemory needs lifecycle-aware review.\n",
                encoding="utf-8",
            )

            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)

            ingest = run_noesis(
                "ingest",
                "source",
                "--vault",
                str(vault_path),
                "--file",
                str(raw_source),
                "--title",
                "Research Note",
                "--slug",
                "research-note",
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            self.assertIn("created source-research-note", ingest.stdout)
            self.assertTrue((vault_path / "raw" / "research-note.md").exists())
            self.assertTrue((vault_path / "sources" / "source-research-note.md").exists())
            validate_after_ingest = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate_after_ingest.returncode, 0, validate_after_ingest.stderr)

            evidence = run_noesis(
                "extract",
                "evidence",
                "--vault",
                str(vault_path),
                "--source",
                "source-research-note",
                "--title",
                "Lifecycle Review Evidence",
                "--evidence",
                "The source says useful memory needs lifecycle-aware review.",
                "--slug",
                "lifecycle-review",
            )
            self.assertEqual(evidence.returncode, 0, evidence.stderr)
            self.assertIn("created evidence-lifecycle-review", evidence.stdout)
            self.assertTrue((vault_path / "evidence" / "evidence-lifecycle-review.md").exists())
            validate_after_evidence = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate_after_evidence.returncode, 0, validate_after_evidence.stderr)

            claim = run_noesis(
                "propose",
                "claim",
                "--vault",
                str(vault_path),
                "--evidence",
                "evidence-lifecycle-review",
                "--title",
                "Memory Needs Review",
                "--claim",
                "Useful memory requires lifecycle-aware review.",
                "--slug",
                "memory-needs-review",
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)
            self.assertIn("created claim-memory-needs-review", claim.stdout)
            self.assertTrue((vault_path / "claims" / "claim-memory-needs-review.md").exists())

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            queue = run_noesis("review", "queue", "--vault", str(vault_path))
            self.assertEqual(queue.returncode, 0, queue.stderr)
            self.assertIn("evidence-lifecycle-review", queue.stdout)
            self.assertIn("claim-memory-needs-review", queue.stdout)
            self.assertIn("ready-for-review", queue.stdout)

            trace = run_noesis("trace", "claim-memory-needs-review", "--vault", str(vault_path))
            self.assertEqual(trace.returncode, 0, trace.stderr)
            self.assertIn("source-research-note", trace.stdout)
            self.assertIn("evidence-lifecycle-review", trace.stdout)
            self.assertIn("claim-memory-needs-review", trace.stdout)

    def test_ingest_source_rejects_invalid_source_date_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "dated-note.md"
            raw_source.write_text("Invalid date should not dirty the vault.\n", encoding="utf-8")

            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)

            ingest = run_noesis(
                "ingest",
                "source",
                "--vault",
                str(vault_path),
                "--file",
                str(raw_source),
                "--title",
                "Dated Note",
                "--source-date",
                "2026/06/06",
            )
            self.assertNotEqual(ingest.returncode, 0)
            self.assertIn("source_date must be YYYY-MM-DD or unknown", ingest.stderr)
            self.assertFalse((vault_path / "raw" / "dated-note.md").exists())
            self.assertEqual(list((vault_path / "sources").glob("source-dated-note*.md")), [])

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_review_queue_lists_stale_ready_note(self) -> None:
        result = run_noesis("review", "queue", "--vault", str(EXAMPLE_VAULT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stale-custom-plugin-first", result.stdout)
        self.assertIn("ready-for-review", result.stdout)

    def test_review_queue_rejects_invalid_vault(self) -> None:
        result = run_noesis("review", "queue", "--vault", "/tmp/noesis-missing-vault")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("vault path does not exist", result.stderr)
        self.assertNotIn("review queue empty", result.stdout)

    def test_trace_finds_full_lifecycle(self) -> None:
        result = run_noesis(
            "trace",
            "reviewed-knowledge-noesis-lifecycle",
            "--vault",
            str(EXAMPLE_VAULT),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in (
            "source-noesis-readme",
            "evidence-memory-lifecycle",
            "claim-useful-memory-requires-lifecycle",
            "synthesis-local-first-lifecycle-interface",
            "review-local-first-lifecycle",
            "reviewed-knowledge-noesis-lifecycle",
            "context-first-cli-mcp-workflow",
        ):
            self.assertIn(expected, result.stdout)

    def test_trace_prefers_note_stems_over_non_note_file_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            source = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            claim = vault_path / "claims" / "foo.md"
            claim.write_text(
                source.read_text(encoding="utf-8").replace(
                    "claim-useful-memory-requires-lifecycle",
                    "claim-foo",
                ),
                encoding="utf-8",
            )
            (vault_path / "raw" / "foo.md").write_text("raw collision\n", encoding="utf-8")

            result = run_noesis("trace", "foo", "--vault", str(vault_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("claim-foo", result.stdout)
            self.assertIn("claims/foo.md", result.stdout)

    def test_trace_and_validation_resolve_frontmatter_alias_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            source = vault_path / "sources" / "source-noesis-readme.md"
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    "aliases: []",
                    "aliases:\n  - README source",
                ),
                encoding="utf-8",
            )
            claim = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            claim.write_text(
                claim.read_text(encoding="utf-8").replace(
                    '  - "[[source-noesis-readme]]"',
                    '  - "[[README source]]"',
                ),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            self.assertEqual(vault.validate(), [])

            result = run_noesis("trace", "README source", "--vault", str(vault_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("source-noesis-readme", result.stdout)
            self.assertIn("claim-useful-memory-requires-lifecycle", result.stdout)

    def test_context_build_uses_reviewed_knowledge_and_excludes_stale(self) -> None:
        result = run_noesis(
            "context",
            "build",
            "--vault",
            str(EXAMPLE_VAULT),
            "--purpose",
            "test context",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Noesis Lifecycle Knowledge", result.stdout)
        self.assertIn("reviewed-knowledge-noesis-lifecycle", result.stdout)
        self.assertNotIn("Build Custom Obsidian Plugin First", result.stdout)
        self.assertNotIn("stale-custom-plugin-first", result.stdout)

    def test_context_build_filters_reviewed_knowledge_by_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            other = vault_path / "knowledge" / "reviewed-knowledge-other-topic.md"
            other.write_text(
                """---
title: Other Topic Knowledge
noesis_id: reviewed-knowledge-other-topic
type: reviewed-knowledge
lifecycle_stage: knowledge
status: active
review_state: reviewed
confidence: high
created: 2026-05-29
updated: 2026-05-29
reviewed_at: 2026-05-29
tags:
  - other-topic
aliases: []
---

# Other Topic Knowledge

## Current Knowledge

This note covers a separate topic for an unrelated handoff.
""",
                encoding="utf-8",
            )

            result = run_noesis(
                "context",
                "build",
                "--vault",
                str(vault_path),
                "--scope",
                "noesis",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Noesis Lifecycle Knowledge", result.stdout)
            self.assertNotIn("Other Topic Knowledge", result.stdout)

    def test_validator_rejects_broken_wikilink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            note_path.write_text(note_path.read_text(encoding="utf-8") + "\n[[missing-note]]\n", encoding="utf-8")

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn("unresolved wikilink [[missing-note]]", issues)

    def test_validator_rejects_relationship_wikilink_to_non_note_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8").replace(
                    '  - "[[source-noesis-readme]]"',
                    '  - "[[raw/2026-05-29-noesis-readme-excerpt]]"',
                ),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn(
                "sources relationship wikilink [[raw/2026-05-29-noesis-readme-excerpt]] does not resolve to a Noesis note",
                issues,
            )

    def test_validator_rejects_bare_relationship_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "context" / "operational-context-first-cli-mcp-workflow.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8").replace(
                    '  - "[[reviewed-knowledge-noesis-lifecycle]]"',
                    "  - reviewed-knowledge-noesis-lifecycle",
                ),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn(
                "reviewed_knowledge relationship entry 'reviewed-knowledge-noesis-lifecycle' must be a wikilink",
                issues,
            )

    def test_validator_rejects_blank_noesis_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8").replace(
                    "noesis_id: claim-useful-memory-requires-lifecycle",
                    'noesis_id: ""',
                ),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn("noesis_id must not be blank", issues)

    def test_validator_allows_same_note_heading_wikilink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "review" / "review-local-first-lifecycle.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8") + "\n[[#Review Notes]]\n",
                encoding="utf-8",
            )

            issues = Vault.load(vault_path).validate()
            self.assertEqual(issues, [])

    def test_validator_rejects_non_note_reviewed_knowledge_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "context" / "operational-context-first-cli-mcp-workflow.md"
            note_text = note_path.read_text(encoding="utf-8")
            note_path.write_text(
                note_text.replace(
                    '  - "[[reviewed-knowledge-noesis-lifecycle]]"',
                    '  - "[[raw/2026-05-29-noesis-readme-excerpt]]"',
                ),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn(
                "reviewed_knowledge relationship wikilink [[raw/2026-05-29-noesis-readme-excerpt]] does not resolve to a Noesis note",
                issues,
            )

    def test_validator_rejects_non_current_reviewed_knowledge_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            knowledge_path = vault_path / "knowledge" / "reviewed-knowledge-noesis-lifecycle.md"
            knowledge_path.write_text(
                knowledge_path.read_text(encoding="utf-8").replace("status: active", "status: complete"),
                encoding="utf-8",
            )

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn(
                "reviewed_knowledge reference '[[reviewed-knowledge-noesis-lifecycle]]' is not current reviewed knowledge",
                issues,
            )


if __name__ == "__main__":
    unittest.main()
