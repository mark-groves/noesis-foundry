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

    def test_validator_rejects_broken_wikilink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "claims" / "claim-useful-memory-requires-lifecycle.md"
            note_path.write_text(note_path.read_text(encoding="utf-8") + "\n[[missing-note]]\n", encoding="utf-8")

            vault = Vault.load(vault_path)
            issues = [issue.message for issue in vault.validate()]
            self.assertIn("unresolved wikilink [[missing-note]]", issues)

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
                "reviewed_knowledge reference '[[raw/2026-05-29-noesis-readme-excerpt]]' does not resolve to a Noesis note",
                issues,
            )


if __name__ == "__main__":
    unittest.main()
