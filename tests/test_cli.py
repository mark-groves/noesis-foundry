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

    def test_full_cli_lifecycle_writes_context_from_fresh_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "memory-source.md"
            raw_source.write_text(
                "# Memory Source\n\nUseful memory needs source-backed review before reuse.\n",
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
                "Memory Source",
                "--slug",
                "memory-source",
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)

            evidence = run_noesis(
                "extract",
                "evidence",
                "--vault",
                str(vault_path),
                "--source",
                "source-memory-source",
                "--title",
                "Source-Backed Review Evidence",
                "--evidence",
                "The source says useful memory needs source-backed review before reuse.",
                "--slug",
                "source-backed-review",
            )
            self.assertEqual(evidence.returncode, 0, evidence.stderr)

            evidence_review = run_noesis(
                "review",
                "approve",
                "evidence-source-backed-review",
                "--vault",
                str(vault_path),
                "--reviewer",
                "test-human",
                "--basis",
                "Evidence accurately reflects the source.",
                "--slug",
                "evidence-source-backed-review",
            )
            self.assertEqual(evidence_review.returncode, 0, evidence_review.stderr)
            self.assertIn("created review-evidence-source-backed-review", evidence_review.stdout)

            claim = run_noesis(
                "propose",
                "claim",
                "--vault",
                str(vault_path),
                "--evidence",
                "evidence-source-backed-review",
                "--title",
                "Memory Needs Review Before Reuse",
                "--claim",
                "Reusable memory should be reviewed against source-backed evidence.",
                "--slug",
                "memory-needs-review-before-reuse",
            )
            self.assertEqual(claim.returncode, 0, claim.stderr)

            claim_review = run_noesis(
                "review",
                "approve",
                "claim-memory-needs-review-before-reuse",
                "--vault",
                str(vault_path),
                "--reviewer",
                "test-human",
                "--basis",
                "Claim is grounded in approved evidence.",
                "--slug",
                "claim-memory-needs-review-before-reuse",
            )
            self.assertEqual(claim_review.returncode, 0, claim_review.stderr)

            synthesis = run_noesis(
                "synthesize",
                "--vault",
                str(vault_path),
                "--claim",
                "claim-memory-needs-review-before-reuse",
                "--title",
                "Review Before Reuse Synthesis",
                "--synthesis",
                "Noesis should reuse memory only after it is grounded and reviewed.",
                "--slug",
                "review-before-reuse",
            )
            self.assertEqual(synthesis.returncode, 0, synthesis.stderr)
            self.assertIn("created synthesis-review-before-reuse", synthesis.stdout)

            synthesis_review = run_noesis(
                "review",
                "approve",
                "synthesis-review-before-reuse",
                "--vault",
                str(vault_path),
                "--reviewer",
                "test-human",
                "--basis",
                "Synthesis follows from the approved claim.",
                "--slug",
                "synthesis-review-before-reuse",
                "--next-review",
                "2026-07-06",
            )
            self.assertEqual(synthesis_review.returncode, 0, synthesis_review.stderr)

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-review-before-reuse",
                "--title",
                "Review Before Reuse Knowledge",
                "--knowledge",
                "Noesis operational context should use reviewed memory, not raw drafts.",
                "--slug",
                "review-before-reuse",
                "--next-review",
                "2026-08-06",
            )
            self.assertEqual(promote.returncode, 0, promote.stderr)
            self.assertIn("created reviewed-knowledge-review-before-reuse", promote.stdout)

            context = run_noesis(
                "context",
                "write",
                "--vault",
                str(vault_path),
                "--purpose",
                "prepare a future agent",
                "--title",
                "Review Before Reuse Context",
                "--slug",
                "review-before-reuse",
                "--next-review",
                "2026-08-06",
            )
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("created context-review-before-reuse", context.stdout)

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            queue = run_noesis("review", "queue", "--vault", str(vault_path))
            self.assertEqual(queue.returncode, 0, queue.stderr)
            self.assertIn("review queue empty", queue.stdout)

            trace = run_noesis("trace", "context-review-before-reuse", "--vault", str(vault_path))
            self.assertEqual(trace.returncode, 0, trace.stderr)
            for expected in (
                "source-memory-source",
                "evidence-source-backed-review",
                "claim-memory-needs-review-before-reuse",
                "synthesis-review-before-reuse",
                "review-synthesis-review-before-reuse",
                "reviewed-knowledge-review-before-reuse",
                "context-review-before-reuse",
            ):
                self.assertIn(expected, trace.stdout)

            context_note = (vault_path / "context" / "context-review-before-reuse.md").read_text(encoding="utf-8")
            self.assertIn("reviewed_knowledge:", context_note)
            self.assertIn("[[reviewed-knowledge-review-before-reuse]]", context_note)
            self.assertIn("Noesis operational context should use reviewed memory", context_note)

    def test_review_request_changes_keeps_note_in_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "review-source.md"
            raw_source.write_text("Review changes source.\n", encoding="utf-8")

            self.assertEqual(run_noesis("vault", "init", str(vault_path)).returncode, 0)
            self.assertEqual(
                run_noesis(
                    "ingest",
                    "source",
                    "--vault",
                    str(vault_path),
                    "--file",
                    str(raw_source),
                    "--title",
                    "Review Source",
                    "--slug",
                    "review-source",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "extract",
                    "evidence",
                    "--vault",
                    str(vault_path),
                    "--source",
                    "source-review-source",
                    "--title",
                    "Review Evidence",
                    "--slug",
                    "review-evidence",
                ).returncode,
                0,
            )

            review = run_noesis(
                "review",
                "request-changes",
                "evidence-review-evidence",
                "--vault",
                str(vault_path),
                "--changes-requested",
                "Replace placeholder evidence with source-backed text.",
                "--slug",
                "review-evidence-change-request",
            )
            self.assertEqual(review.returncode, 0, review.stderr)

            queue = run_noesis("review", "queue", "--vault", str(vault_path))
            self.assertEqual(queue.returncode, 0, queue.stderr)
            self.assertIn("evidence-review-evidence", queue.stdout)
            self.assertIn("changes-requested", queue.stdout)

    def test_review_request_changes_invalidates_dependent_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            review = run_noesis(
                "review",
                "request-changes",
                "claim-useful-memory-requires-lifecycle",
                "--vault",
                str(vault_path),
                "--changes-requested",
                "Revise this claim before it can support reviewed knowledge.",
                "--slug",
                "claim-lifecycle-changes",
            )
            self.assertEqual(review.returncode, 0, review.stderr)

            context = run_noesis("context", "build", "--vault", str(vault_path))
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("No current reviewed knowledge found.", context.stdout)
            self.assertNotIn("Noesis should represent memory as a lifecycle", context.stdout)

            knowledge_note = (
                vault_path / "knowledge" / "reviewed-knowledge-noesis-lifecycle.md"
            ).read_text(encoding="utf-8")
            self.assertIn("status: needs-review", knowledge_note)
            self.assertIn("review_state: changes-requested", knowledge_note)

            context_note = (
                vault_path / "context" / "operational-context-first-cli-mcp-workflow.md"
            ).read_text(encoding="utf-8")
            self.assertIn("reviewed_knowledge: []", context_note)
            self.assertIn("No current reviewed knowledge found.", context_note)
            self.assertNotIn("Build CLI commands against the vault schema", context_note)

    def test_promote_rejects_unapproved_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "unapproved-source.md"
            raw_source.write_text("Unapproved promotion source.\n", encoding="utf-8")

            self.assertEqual(run_noesis("vault", "init", str(vault_path)).returncode, 0)
            self.assertEqual(
                run_noesis(
                    "ingest",
                    "source",
                    "--vault",
                    str(vault_path),
                    "--file",
                    str(raw_source),
                    "--title",
                    "Unapproved Source",
                    "--slug",
                    "unapproved-source",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "extract",
                    "evidence",
                    "--vault",
                    str(vault_path),
                    "--source",
                    "source-unapproved-source",
                    "--title",
                    "Unapproved Evidence",
                    "--slug",
                    "unapproved-evidence",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "review",
                    "approve",
                    "evidence-unapproved-evidence",
                    "--vault",
                    str(vault_path),
                    "--slug",
                    "unapproved-evidence",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "propose",
                    "claim",
                    "--vault",
                    str(vault_path),
                    "--evidence",
                    "evidence-unapproved-evidence",
                    "--title",
                    "Unapproved Claim",
                    "--slug",
                    "unapproved-claim",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "review",
                    "approve",
                    "claim-unapproved-claim",
                    "--vault",
                    str(vault_path),
                    "--slug",
                    "unapproved-claim",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "synthesize",
                    "--vault",
                    str(vault_path),
                    "--claim",
                    "claim-unapproved-claim",
                    "--title",
                    "Unapproved Synthesis",
                    "--slug",
                    "unapproved-synthesis",
                ).returncode,
                0,
            )

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-unapproved-synthesis",
                "--title",
                "Should Not Promote",
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("synthesis must be approved before promotion", promote.stderr)
            self.assertEqual(list((vault_path / "knowledge").glob("reviewed-knowledge-should-not-promote*.md")), [])

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_promote_rejects_ungrounded_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)
            (vault_path / "review" / "review-ungrounded-synthesis.md").write_text(
                """---
title: Review Ungrounded Synthesis
noesis_id: review-ungrounded-synthesis
type: review
lifecycle_stage: review
status: complete
review_state: approved
confidence: medium
created: 2026-06-06
updated: 2026-06-06
reviewer: test
reviewed_at: 2026-06-06
reviewed_notes:
  - "[[synthesis-ungrounded]]"
decision: approved
tags:
  - noesis
  - review
aliases: []
---

# Review Ungrounded Synthesis
""",
                encoding="utf-8",
            )
            (vault_path / "syntheses" / "synthesis-ungrounded.md").write_text(
                """---
title: Ungrounded Synthesis
noesis_id: synthesis-ungrounded
type: synthesis
lifecycle_stage: synthesis
status: reviewed
review_state: approved
confidence: medium
created: 2026-06-06
updated: 2026-06-06
reviewed_by:
  - "[[review-ungrounded-synthesis]]"
tags:
  - noesis
  - synthesis
aliases: []
---

# Ungrounded Synthesis

## Synthesis

This approved-looking synthesis has no source, evidence, or claim lineage.
""",
                encoding="utf-8",
            )
            validate_before_promote = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate_before_promote.returncode, 0, validate_before_promote.stderr)

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-ungrounded",
                "--title",
                "Should Not Promote",
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("synthesis must preserve source, evidence, and claim lineage", promote.stderr)
            self.assertEqual(list((vault_path / "knowledge").glob("reviewed-knowledge-should-not-promote*.md")), [])

    def test_review_approve_rejects_stale_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            stale = run_noesis(
                "memory",
                "stale",
                "reviewed-knowledge-noesis-lifecycle",
                "--vault",
                str(vault_path),
                "--reason",
                "This knowledge was superseded and needs an explicit restore flow.",
                "--slug",
                "reviewed-knowledge-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)

            review = run_noesis(
                "review",
                "approve",
                "reviewed-knowledge-noesis-lifecycle",
                "--vault",
                str(vault_path),
                "--slug",
                "stale-knowledge-approval",
            )
            self.assertNotEqual(review.returncode, 0)
            self.assertIn("stale, superseded, or archived memory cannot be approved", review.stderr)
            self.assertEqual(list((vault_path / "review").glob("review-stale-knowledge-approval*.md")), [])

    def test_review_approve_allows_stale_memory_audit_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            review = run_noesis(
                "review",
                "approve",
                "stale-custom-plugin-first",
                "--vault",
                str(vault_path),
                "--basis",
                "Stale-memory audit is still valid.",
                "--slug",
                "stale-audit-approval",
            )
            self.assertEqual(review.returncode, 0, review.stderr)

            stale_note = (vault_path / "stale" / "stale-custom-plugin-first.md").read_text(encoding="utf-8")
            self.assertIn("status: superseded", stale_note)
            self.assertIn("review_state: approved", stale_note)
            self.assertIn("review-stale-audit-approval", stale_note)

            queue = run_noesis("review", "queue", "--vault", str(vault_path))
            self.assertEqual(queue.returncode, 0, queue.stderr)
            self.assertNotIn("stale-custom-plugin-first", queue.stdout)

    def test_promote_rejects_stale_claim_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            stale = run_noesis(
                "memory",
                "stale",
                "claim-useful-memory-requires-lifecycle",
                "--vault",
                str(vault_path),
                "--reason",
                "The claim is no longer valid support for promotion.",
                "--slug",
                "lifecycle-claim-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-local-first-lifecycle-interface",
                "--title",
                "Should Not Promote",
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("synthesis claims must be approved before knowledge promotion", promote.stderr)
            self.assertEqual(list((vault_path / "knowledge").glob("reviewed-knowledge-should-not-promote*.md")), [])

    def test_promote_rejects_stale_evidence_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            stale = run_noesis(
                "memory",
                "stale",
                "evidence-memory-lifecycle",
                "--vault",
                str(vault_path),
                "--reason",
                "The evidence is no longer current support for promotion.",
                "--slug",
                "lifecycle-evidence-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-local-first-lifecycle-interface",
                "--title",
                "Should Not Promote",
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn(
                "synthesis source and evidence lineage must be current before knowledge promotion",
                promote.stderr,
            )
            self.assertEqual(list((vault_path / "knowledge").glob("reviewed-knowledge-should-not-promote*.md")), [])

    def test_promote_rejects_unreviewed_evidence_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "draft-evidence-source.md"
            raw_source.write_text("Promotion source with draft evidence.\n", encoding="utf-8")

            self.assertEqual(run_noesis("vault", "init", str(vault_path)).returncode, 0)
            self.assertEqual(
                run_noesis(
                    "ingest",
                    "source",
                    "--vault",
                    str(vault_path),
                    "--file",
                    str(raw_source),
                    "--title",
                    "Draft Evidence Source",
                    "--slug",
                    "draft-evidence-source",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "extract",
                    "evidence",
                    "--vault",
                    str(vault_path),
                    "--source",
                    "source-draft-evidence-source",
                    "--title",
                    "Draft Evidence",
                    "--evidence",
                    "This evidence has not been reviewed.",
                    "--slug",
                    "draft-evidence",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "propose",
                    "claim",
                    "--vault",
                    str(vault_path),
                    "--evidence",
                    "evidence-draft-evidence",
                    "--title",
                    "Claim On Draft Evidence",
                    "--claim",
                    "This claim should not be promotable yet.",
                    "--slug",
                    "draft-evidence-claim",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "review",
                    "approve",
                    "claim-draft-evidence-claim",
                    "--vault",
                    str(vault_path),
                    "--slug",
                    "draft-evidence-claim",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "synthesize",
                    "--vault",
                    str(vault_path),
                    "--claim",
                    "claim-draft-evidence-claim",
                    "--title",
                    "Synthesis On Draft Evidence",
                    "--slug",
                    "draft-evidence-synthesis",
                ).returncode,
                0,
            )
            self.assertEqual(
                run_noesis(
                    "review",
                    "approve",
                    "synthesis-draft-evidence-synthesis",
                    "--vault",
                    str(vault_path),
                    "--slug",
                    "draft-evidence-synthesis",
                ).returncode,
                0,
            )

            promote = run_noesis(
                "knowledge",
                "promote",
                "--vault",
                str(vault_path),
                "--synthesis",
                "synthesis-draft-evidence-synthesis",
                "--title",
                "Should Not Promote",
            )
            self.assertNotEqual(promote.returncode, 0)
            self.assertIn("synthesis evidence must be approved before knowledge promotion", promote.stderr)
            self.assertEqual(list((vault_path / "knowledge").glob("reviewed-knowledge-should-not-promote*.md")), [])

    def test_mark_memory_stale_excludes_existing_context_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            stale = run_noesis(
                "memory",
                "stale",
                "reviewed-knowledge-noesis-lifecycle",
                "--vault",
                str(vault_path),
                "--reason",
                "The lifecycle contract changed and this knowledge needs replacement.",
                "--superseded-by",
                "synthesis-local-first-lifecycle-interface",
                "--slug",
                "noesis-lifecycle-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)
            self.assertIn("created stale-noesis-lifecycle-old", stale.stdout)

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            context = run_noesis("context", "build", "--vault", str(vault_path))
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("No current reviewed knowledge found.", context.stdout)
            self.assertNotIn("Noesis should represent memory as a lifecycle", context.stdout)

            context_note = (
                vault_path / "context" / "operational-context-first-cli-mcp-workflow.md"
            ).read_text(encoding="utf-8")
            self.assertIn("excluded_memory:", context_note)
            self.assertIn("[[stale-custom-plugin-first]]", context_note)
            self.assertIn('[[reviewed-knowledge-noesis-lifecycle]]', context_note)
            self.assertIn('[[stale-noesis-lifecycle-old]]', context_note)
            self.assertNotIn("Noesis should represent memory as a lifecycle", context_note)

    def test_mark_synthesis_stale_excludes_existing_context_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            stale = run_noesis(
                "memory",
                "stale",
                "synthesis-local-first-lifecycle-interface",
                "--vault",
                str(vault_path),
                "--reason",
                "The synthesis has been replaced by a narrower implementation contract.",
                "--slug",
                "lifecycle-synthesis-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)
            self.assertIn("created stale-lifecycle-synthesis-old", stale.stdout)

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            context = run_noesis("context", "build", "--vault", str(vault_path))
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("No current reviewed knowledge found.", context.stdout)
            self.assertNotIn("Noesis should represent memory as a lifecycle", context.stdout)

            knowledge_note = (
                vault_path / "knowledge" / "reviewed-knowledge-noesis-lifecycle.md"
            ).read_text(encoding="utf-8")
            self.assertIn("status: stale", knowledge_note)

            context_note = (
                vault_path / "context" / "operational-context-first-cli-mcp-workflow.md"
            ).read_text(encoding="utf-8")
            self.assertIn("reviewed_knowledge: []", context_note)
            self.assertIn("syntheses: []", context_note)
            self.assertIn("[[synthesis-local-first-lifecycle-interface]]", context_note)
            self.assertIn("[[reviewed-knowledge-noesis-lifecycle]]", context_note)
            self.assertIn("[[stale-lifecycle-synthesis-old]]", context_note)
            self.assertIn("No current reviewed knowledge found.", context_note)
            self.assertNotIn("Build CLI commands against the vault schema", context_note)

    def test_mark_stale_preserves_context_scope_and_purpose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            context = run_noesis(
                "context",
                "write",
                "--vault",
                str(vault_path),
                "--scope",
                "lifecycle",
                "--purpose",
                "prepare scoped agent",
                "--slug",
                "scoped-lifecycle",
            )
            self.assertEqual(context.returncode, 0, context.stderr)

            stale = run_noesis(
                "memory",
                "stale",
                "synthesis-local-first-lifecycle-interface",
                "--vault",
                str(vault_path),
                "--reason",
                "The synthesis has been replaced.",
                "--slug",
                "scoped-lifecycle-synthesis-old",
            )
            self.assertEqual(stale.returncode, 0, stale.stderr)

            context_note = (vault_path / "context" / "context-scoped-lifecycle.md").read_text(encoding="utf-8")
            self.assertIn("scope: lifecycle", context_note)
            self.assertIn("purpose: prepare scoped agent", context_note)
            self.assertIn("Scope: lifecycle", context_note)
            self.assertIn("Purpose: prepare scoped agent", context_note)
            self.assertIn("No current reviewed knowledge found.", context_note)

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

    def test_draft_commands_reject_blank_titles_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "draft-source.md"
            raw_source.write_text("Draft title validation source.\n", encoding="utf-8")

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
                "Draft Source",
                "--slug",
                "draft-source",
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)

            evidence = run_noesis(
                "extract",
                "evidence",
                "--vault",
                str(vault_path),
                "--source",
                "source-draft-source",
                "--title",
                "   ",
            )
            self.assertNotEqual(evidence.returncode, 0)
            self.assertIn("title must not be blank", evidence.stderr)
            self.assertEqual(list((vault_path / "evidence").glob("evidence-*.md")), [])

            valid_evidence = run_noesis(
                "extract",
                "evidence",
                "--vault",
                str(vault_path),
                "--source",
                "source-draft-source",
                "--title",
                "Draft Evidence",
                "--slug",
                "draft-evidence",
            )
            self.assertEqual(valid_evidence.returncode, 0, valid_evidence.stderr)

            claim = run_noesis(
                "propose",
                "claim",
                "--vault",
                str(vault_path),
                "--evidence",
                "evidence-draft-evidence",
                "--title",
                "   ",
            )
            self.assertNotEqual(claim.returncode, 0)
            self.assertIn("title must not be blank", claim.stderr)
            self.assertEqual(list((vault_path / "claims").glob("claim-*.md")), [])

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_failed_evidence_validation_rolls_back_written_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            raw_source = tmp_path / "rollback-source.md"
            raw_source.write_text("Rollback validation source.\n", encoding="utf-8")

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
                "Rollback Source",
                "--slug",
                "rollback-source",
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)

            evidence = run_noesis(
                "extract",
                "evidence",
                "--vault",
                str(vault_path),
                "--source",
                "source-rollback-source",
                "--title",
                "Rollback Evidence",
                "--slug",
                "rollback-evidence",
                "--evidence",
                "This invalid draft points to [[missing-note]].",
            )
            self.assertNotEqual(evidence.returncode, 0)
            self.assertIn("unresolved wikilink [[missing-note]]", evidence.stderr)
            self.assertFalse((vault_path / "evidence" / "evidence-rollback-evidence.md").exists())

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_propose_claim_rejects_evidence_without_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"

            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)
            (vault_path / "evidence" / "evidence-ungrounded.md").write_text(
                """---
title: Ungrounded Evidence
noesis_id: evidence-ungrounded
type: evidence
lifecycle_stage: evidence
status: extracted
review_state: ready-for-review
confidence: medium
created: 2026-06-06
updated: 2026-06-06
tags:
  - noesis
  - evidence
aliases: []
---

# Ungrounded Evidence

## Evidence

This legacy evidence note does not link to a source.
""",
                encoding="utf-8",
            )
            validate_before_claim = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate_before_claim.returncode, 0, validate_before_claim.stderr)

            claim = run_noesis(
                "propose",
                "claim",
                "--vault",
                str(vault_path),
                "--evidence",
                "evidence-ungrounded",
                "--title",
                "Ungrounded Claim",
            )
            self.assertNotEqual(claim.returncode, 0)
            self.assertIn("claim evidence must link to at least one source note", claim.stderr)
            self.assertEqual(list((vault_path / "claims").glob("claim-*.md")), [])

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
