from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from noesis.mcp_server import NoesisMcpHandlers
from noesis.vault import (
    Vault,
    extract_evidence,
    mark_memory_stale,
    promote_synthesis,
    propose_claim,
    renew_review,
    request_review_changes,
    synthesize_claims,
    write_note,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"
VICTIM_ID = "evidence-project-memory-corpus-unreviewed-import-draft"
KNOWLEDGE_ID = "reviewed-knowledge-project-memory-corpus-continuation"
KNOWLEDGE_ALIAS = "project memory corpus continuation knowledge"


def run_noesis(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "noesis", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def copy_example_vault(tmp: str) -> Path:
    vault_path = Path(tmp) / "vault"
    shutil.copytree(EXAMPLE_VAULT, vault_path)
    return vault_path


def write_plant(vault_path: Path, relative: str, note_id: str, aliases: list[str], marker: str) -> None:
    write_note(
        vault_path / relative,
        {
            "title": "Planted Reviewed Knowledge",
            "noesis_id": note_id,
            "type": "reviewed-knowledge",
            "lifecycle_stage": "knowledge",
            "status": "needs-review",
            "review_state": "ready-for-review",
            "confidence": "high",
            "created": "2026-06-18",
            "updated": "2026-06-18",
            "sources": ["[[source-project-memory-corpus-repo-artifacts]]"],
            "evidence": ["[[evidence-project-memory-corpus-contract]]"],
            "claims": ["[[claim-project-memory-corpus-continuation]]"],
            "syntheses": ["[[synthesis-project-memory-corpus-continuation]]"],
            "reviewed_by": ["[[review-project-memory-corpus-continuation]]"],
            "tags": ["noesis", "knowledge"],
            "aliases": aliases,
        },
        f"# Planted Reviewed Knowledge\n\n{marker}\n",
    )


class NoteIdentityTests(unittest.TestCase):
    def test_alias_collision_cannot_steal_exact_id(self) -> None:
        self.assert_plant_cannot_steal_id(
            "knowledge/zzz-alias-pwn.md",
            "reviewed-knowledge-zzz-alias-pwn",
            [VICTIM_ID],
            "ATTACKER_TRUSTED_TEXT_ALIAS_PWN",
        )

    def test_stem_collision_cannot_steal_exact_id(self) -> None:
        self.assert_plant_cannot_steal_id(
            f"knowledge/{VICTIM_ID}.md",
            "reviewed-knowledge-stem-pwn",
            [],
            "ATTACKER_TRUSTED_TEXT_STEM_PWN",
        )

    def test_earlier_path_alias_matching_id_is_rejected(self) -> None:
        self.assert_plant_cannot_steal_id(
            "claims/aaa-alias-pwn.md",
            "reviewed-knowledge-aaa-alias-pwn",
            [VICTIM_ID],
            "ATTACKER_TRUSTED_TEXT_EARLY_ALIAS",
        )

    def test_display_alias_cannot_steal_exact_id(self) -> None:
        self.assert_plant_cannot_steal_id(
            "knowledge/zzz-display-pwn.md",
            "reviewed-knowledge-zzz-display-pwn",
            [f"{VICTIM_ID}|planted"],
            "ATTACKER_TRUSTED_TEXT_DISPLAY_ALIAS",
        )

    def test_padded_alias_cannot_steal_exact_id(self) -> None:
        self.assert_plant_cannot_steal_id(
            "knowledge/zzz-padded-pwn.md",
            "reviewed-knowledge-zzz-padded-pwn",
            [f" {VICTIM_ID} "],
            "ATTACKER_TRUSTED_TEXT_PADDED_ALIAS",
        )

    def test_path_alias_cannot_redirect_note_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = copy_example_vault(tmp)
            victim_path = f"evidence/{VICTIM_ID}.md"
            victim_stem_path = f"evidence/{VICTIM_ID}"
            write_plant(
                vault_path,
                "claims/aaa-path-pwn.md",
                "reviewed-knowledge-aaa-path-pwn",
                [victim_path, victim_stem_path],
                "ATTACKER_TRUSTED_TEXT_PATH_ALIAS",
            )

            vault = Vault.load(vault_path)
            for ref in (victim_path, victim_stem_path, VICTIM_ID):
                resolved = vault.find_note(ref)
                self.assertIsNotNone(resolved, ref)
                assert resolved is not None
                self.assertEqual(resolved.rel_path.as_posix(), victim_path, ref)

            issues = [issue.format(vault_path) for issue in vault.validate()]
            self.assertTrue(
                any(victim_path in issue and "duplicate lookup key" in issue for issue in issues),
                issues,
            )
            self.assertTrue(
                any(victim_stem_path in issue and "duplicate lookup key" in issue for issue in issues),
                issues,
            )

    def test_duplicate_noesis_id_keeps_earlier_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = copy_example_vault(tmp)
            source = (vault_path / "evidence" / f"{VICTIM_ID}.md").read_text(encoding="utf-8")
            (vault_path / "knowledge" / "zzz-duplicate-id.md").write_text(source, encoding="utf-8")

            vault = Vault.load(vault_path)
            resolved = vault.find_note_by_id(VICTIM_ID)
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved.rel_path.as_posix(), f"evidence/{VICTIM_ID}.md")
            self.assertTrue(any("duplicate noesis_id" in issue.message for issue in vault.validate()))
            traced = run_noesis("trace", VICTIM_ID, "--vault", str(vault_path), "--json")
            self.assertEqual(traced.returncode, 0, traced.stderr)
            traced_paths = [
                note["path"] for note in json.loads(traced.stdout)["notes"] if note["noesis_id"] == VICTIM_ID
            ]
            self.assertEqual(traced_paths, [f"evidence/{VICTIM_ID}.md"])

            approved = run_noesis(
                "review",
                "approve",
                VICTIM_ID,
                "--vault",
                str(vault_path),
                "--reviewer",
                "Ada Lovelace",
                "--basis",
                "duplicate ids must not select the later file",
                "--json",
            )
            self.assertNotEqual(approved.returncode, 0, approved.stdout)
            self.assertEqual(Vault.load(vault_path).by_id[VICTIM_ID].status, "extracted")

    def test_duplicate_human_alias_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = copy_example_vault(tmp)
            readme = vault_path / "sources" / "source-noesis-readme.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "  - README source\n",
                    "  - README source\n  - shared label\n",
                    1,
                ),
                encoding="utf-8",
            )
            loop = vault_path / "sources" / "source-cli-authoring-loop.md"
            loop.write_text(
                loop.read_text(encoding="utf-8").replace("aliases: []", "aliases:\n  - shared label", 1),
                encoding="utf-8",
            )

            issues = Vault.load(vault_path).validate()

            self.assertTrue(
                any("duplicate lookup key 'shared label'" in issue.message for issue in issues),
                [issue.message for issue in issues],
            )

    def test_human_alias_resolves_wikilinks_but_not_trust_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = copy_example_vault(tmp)
            vault = Vault.load(vault_path)
            linked = vault.find_note(KNOWLEDGE_ALIAS)
            self.assertIsNotNone(linked)
            assert linked is not None
            self.assertEqual(linked.noesis_id, KNOWLEDGE_ID)

            handlers = NoesisMcpHandlers(default_vault=vault_path)
            fetched = handlers.get_note(KNOWLEDGE_ALIAS)
            self.assertFalse(fetched["ok"])
            self.assertIn("note not found", fetched["error"])
            by_id = handlers.get_note(KNOWLEDGE_ID)
            self.assertTrue(by_id["ok"], by_id)
            self.assertEqual(by_id["note"]["noesis_id"], KNOWLEDGE_ID)

            shown = handlers.show_review(KNOWLEDGE_ALIAS)
            self.assertFalse(shown["ok"])
            self.assertIn("note not found", shown["error"])

            traced = run_noesis("trace", KNOWLEDGE_ALIAS, "--vault", str(vault_path))
            self.assertNotEqual(traced.returncode, 0, traced.stdout)
            self.assertNotIn(KNOWLEDGE_ID, traced.stdout)
            traced_id = run_noesis("trace", KNOWLEDGE_ID, "--vault", str(vault_path))
            self.assertEqual(traced_id.returncode, 0, traced_id.stderr)
            self.assertIn(KNOWLEDGE_ID, traced_id.stdout)

            for command in (
                lambda: promote_synthesis(vault_path, KNOWLEDGE_ALIAS),
                lambda: mark_memory_stale(vault_path, KNOWLEDGE_ALIAS, reason="retire this alias"),
                lambda: mark_memory_stale(
                    vault_path,
                    KNOWLEDGE_ID,
                    reason="retire this alias",
                    superseded_by=KNOWLEDGE_ALIAS,
                ),
                lambda: extract_evidence(vault_path, KNOWLEDGE_ALIAS),
                lambda: propose_claim(vault_path, [KNOWLEDGE_ALIAS]),
                lambda: synthesize_claims(vault_path, [KNOWLEDGE_ALIAS]),
                lambda: request_review_changes(
                    vault_path,
                    KNOWLEDGE_ALIAS,
                    reviewer="Ada Lovelace",
                    basis="alias must not select this note",
                    changes_requested="use the noesis_id",
                ),
                lambda: renew_review(
                    vault_path,
                    KNOWLEDGE_ALIAS,
                    next_review="2026-08-01",
                    reviewer="Ada Lovelace",
                    basis="still current",
                ),
            ):
                with self.subTest(command=command):
                    with self.assertRaises(ValueError) as raised:
                        command()
                    self.assertIn("not found", str(raised.exception))

            approved = run_noesis(
                "review",
                "approve",
                KNOWLEDGE_ALIAS,
                "--vault",
                str(vault_path),
                "--reviewer",
                "Ada Lovelace",
                "--basis",
                "alias must not select this note",
            )
            self.assertNotEqual(approved.returncode, 0, approved.stdout)
            self.assertIn("not found", approved.stderr)
            reloaded = Vault.load(vault_path)
            self.assertEqual(reloaded.by_id[KNOWLEDGE_ID].status, "active")
            self.assertEqual(reloaded.find_note(KNOWLEDGE_ALIAS).noesis_id, KNOWLEDGE_ID)

    def assert_plant_cannot_steal_id(
        self,
        relative: str,
        plant_id: str,
        aliases: list[str],
        marker: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = copy_example_vault(tmp)
            write_plant(vault_path, relative, plant_id, aliases, marker)
            vault = Vault.load(vault_path)
            resolved = vault.find_note(VICTIM_ID)
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved.noesis_id, VICTIM_ID)
            self.assertNotEqual(resolved.rel_path.as_posix(), relative)

            issues = vault.validate()
            self.assertTrue(
                any(VICTIM_ID in issue.message and "matches noesis_id" in issue.message for issue in issues),
                [issue.format(vault_path) for issue in issues],
            )

            handlers = NoesisMcpHandlers(default_vault=vault_path)
            fetched = handlers.get_note(VICTIM_ID)
            self.assertFalse(fetched["ok"], fetched)
            self.assertNotIn(plant_id, json.dumps(fetched))
            shown = handlers.show_review(VICTIM_ID)
            self.assertFalse(shown["ok"], shown)
            self.assertNotIn(plant_id, json.dumps(shown))

            traced = run_noesis("trace", VICTIM_ID, "--vault", str(vault_path), "--json")
            self.assertEqual(traced.returncode, 0, traced.stderr)
            traced_by_id = {note["noesis_id"]: note for note in json.loads(traced.stdout)["notes"]}
            self.assertEqual(traced_by_id[VICTIM_ID]["path"], f"evidence/{VICTIM_ID}.md")
            self.assertNotEqual(traced_by_id.get(plant_id, {}).get("path"), f"evidence/{VICTIM_ID}.md")

            approved = run_noesis(
                "review",
                "approve",
                VICTIM_ID,
                "--vault",
                str(vault_path),
                "--reviewer",
                "Ada Lovelace",
                "--basis",
                "the queued evidence is the note with this id",
                "--json",
            )
            self.assertNotEqual(approved.returncode, 0, approved.stdout)
            self.assertNotIn(plant_id, approved.stdout + approved.stderr)
            approved_payload = json.loads(approved.stdout)
            self.assertFalse(approved_payload["ok"])
            mcp_approved = handlers.approve_review(
                VICTIM_ID,
                reviewer="Ada Lovelace",
                basis="the queued evidence is the note with this id",
            )
            self.assertFalse(mcp_approved["ok"], mcp_approved)
            self.assertNotIn(plant_id, json.dumps(mcp_approved))

            reloaded = Vault.load(vault_path)
            knowledge_ids = [note.noesis_id for note in reloaded.current_reviewed_knowledge()]
            self.assertNotIn(plant_id, knowledge_ids)
            self.assertEqual(reloaded.by_id[VICTIM_ID].status, "extracted")
            self.assertEqual(reloaded.by_id[plant_id].status, "needs-review")

            built = run_noesis("context", "build", "--vault", str(vault_path), "--json")
            self.assertNotEqual(built.returncode, 0, built.stdout)
            self.assertNotIn(marker, built.stdout)
            self.assertNotIn(plant_id, built.stdout)
