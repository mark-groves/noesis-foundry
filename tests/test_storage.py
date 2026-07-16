from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from noesis.storage import atomic_write_text, vault_lock
from noesis.vault import Vault, init_vault


ROOT = Path(__file__).resolve().parents[1]


class StorageTests(unittest.TestCase):
    def test_atomic_write_replaces_content_without_temp_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            atomic_write_text(path, "first\n")
            atomic_write_text(path, "second\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "second\n")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_generic_vault_lock_does_not_create_invalid_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing-vault"
            with self.assertRaisesRegex(ValueError, "vault path is not a directory"):
                with vault_lock(missing):
                    pass
            self.assertFalse(missing.exists())

            invalid_file = root / "not-a-vault"
            invalid_file.write_text("not a directory\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "vault path is not a directory"):
                with vault_lock(invalid_file):
                    pass

    def test_parallel_cli_writers_leave_a_valid_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault_path = root / "vault"
            init_vault(vault_path)
            sources = [root / "alpha.txt", root / "beta.txt"]
            for source in sources:
                source.write_text(f"content for {source.stem}\n", encoding="utf-8")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "noesis",
                        "ingest",
                        "source",
                        "--vault",
                        str(vault_path),
                        "--file",
                        str(source),
                    ],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for source in sources
            ]
            results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
            self.assertEqual([result[2] for result in results], [0, 0], results)
            self.assertEqual(Vault.load(vault_path).validate(), [])
            self.assertIsNotNone(Vault.load(vault_path).find_note("source-alpha"))
            self.assertIsNotNone(Vault.load(vault_path).find_note("source-beta"))
