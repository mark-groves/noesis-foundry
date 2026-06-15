from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from noesis.mcp_server import NoesisMcpHandlers, create_server
from noesis.vault import Vault, build_context, init_vault


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"
CODEX_SESSION_BUNDLE = ROOT / "tests" / "fixtures" / "codex-session-bundle"


class RecordingFastMCP:
    instances: list["RecordingFastMCP"] = []

    def __init__(self, name: str, **kwargs: object) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, object] = {}
        self.resources: dict[str, object] = {}
        self.runs: list[dict[str, object]] = []
        self.instances.append(self)

    def tool(self) -> object:
        def register(function: object) -> object:
            self.tools[getattr(function, "__name__")] = function
            return function

        return register

    def resource(self, uri: str) -> object:
        def register(function: object) -> object:
            self.resources[uri] = function
            return function

        return register

    def run(self, **kwargs: object) -> None:
        self.runs.append(kwargs)


def fake_fastmcp_modules() -> dict[str, types.ModuleType]:
    mcp = types.ModuleType("mcp")
    server = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = RecordingFastMCP
    return {"mcp": mcp, "mcp.server": server, "mcp.server.fastmcp": fastmcp}


class NoesisMcpHandlerTests(unittest.TestCase):
    def test_create_server_registers_expected_mcp_surface(self) -> None:
        # FastMCP does not expose a stable public introspection API across all
        # installed versions, so this smoke test records Noesis' registration
        # calls without starting the long-running stdio transport.
        RecordingFastMCP.instances = []

        with patch.dict(sys.modules, fake_fastmcp_modules()):
            server = create_server(EXAMPLE_VAULT)

        self.assertIsInstance(server, RecordingFastMCP)
        self.assertEqual(server.name, "Noesis Foundry")
        self.assertEqual(server.kwargs, {"json_response": True})
        self.assertEqual(
            sorted(server.tools),
            [
                "noesis_approve_review",
                "noesis_build_context",
                "noesis_create_claim_draft",
                "noesis_create_evidence_draft",
                "noesis_create_synthesis_draft",
                "noesis_get_note",
                "noesis_get_review_queue",
                "noesis_get_review_summary",
                "noesis_import_source_bundle",
                "noesis_ingest_source",
                "noesis_lint_vault",
                "noesis_mark_memory_stale",
                "noesis_promote_synthesis",
                "noesis_renew_review",
                "noesis_request_review_changes",
                "noesis_search_notes",
                "noesis_show_review",
                "noesis_trace_lineage",
                "noesis_write_context",
            ],
        )
        self.assertEqual(sorted(server.resources), ["noesis://note/{note}", "noesis://vault/summary"])

        lint = server.tools["noesis_lint_vault"]()
        self.assertTrue(lint["ok"], lint)
        summary = server.resources["noesis://vault/summary"]()
        self.assertTrue(summary["ok"], summary)
        self.assertGreater(summary["note_count"], 0)

    def test_read_tools_return_structured_example_vault_data(self) -> None:
        handlers = NoesisMcpHandlers(EXAMPLE_VAULT)

        lint = handlers.lint_vault()
        self.assertTrue(lint["ok"], lint)
        self.assertEqual(lint["issue_count"], 0)
        self.assertGreater(lint["note_count"], 0)
        self.assertEqual(lint["contract"]["version"], "1")
        self.assertEqual(lint["compatible"], True)
        self.assertEqual(lint["complete"], True)
        self.assertEqual(lint["ready_for_cli_mcp"], True)

        queue = handlers.get_review_queue()
        self.assertTrue(queue["ok"], queue)
        queue_ids = [note["noesis_id"] for note in queue["notes"]]
        expected_ids = [note.noesis_id for note in Vault.load(EXAMPLE_VAULT).review_queue()]
        self.assertEqual(queue_ids, expected_ids)
        self.assertIn("stale-custom-plugin-first", queue_ids)

        due_queue = handlers.get_review_queue(note_type="stale-memory", due=True, due_on="2026-06-13")
        self.assertTrue(due_queue["ok"], due_queue)
        self.assertEqual([note["noesis_id"] for note in due_queue["notes"]], ["stale-custom-plugin-first"])
        self.assertEqual(due_queue["filters"]["type"], "stale-memory")
        scheduled_due_queue = handlers.get_review_queue(due_on="2026-06-29")
        self.assertTrue(scheduled_due_queue["ok"], scheduled_due_queue)
        scheduled_due_ids = [note["noesis_id"] for note in scheduled_due_queue["notes"]]
        self.assertIn("reviewed-knowledge-noesis-lifecycle", scheduled_due_ids)
        self.assertIn("context-first-cli-mcp-workflow", scheduled_due_ids)
        self.assertNotIn("review-local-first-lifecycle", scheduled_due_ids)
        self.assertNotIn("review-queue", scheduled_due_ids)

        summary = handlers.get_review_summary(due_on="2026-06-13")
        self.assertTrue(summary["ok"], summary)
        self.assertGreaterEqual(summary["pending_count"], 1)
        self.assertIn("stale-custom-plugin-first", [note["noesis_id"] for note in summary["due_notes"]])

        workbench = handlers.show_review("claim-useful-memory-requires-lifecycle", due_on="2026-06-13")
        self.assertTrue(workbench["ok"], workbench)
        self.assertTrue(workbench["audit_status"]["ok"], workbench["audit_status"])
        self.assertIn("evidence", workbench["support"])
        self.assertIn(
            "reviewed-knowledge-noesis-lifecycle",
            [note["noesis_id"] for note in workbench["impact"]["dependent_reviewed_knowledge"]],
        )
        self.assertIn(
            "context-first-cli-mcp-workflow",
            [note["noesis_id"] for note in workbench["impact"]["dependent_contexts"]],
        )
        stale_workbench = handlers.show_review("stale-custom-plugin-first")
        self.assertTrue(stale_workbench["ok"], stale_workbench)
        self.assertIn(
            "context-first-cli-mcp-workflow",
            [note["noesis_id"] for note in stale_workbench["impact"]["dependent_contexts"]],
        )
        for note_id in ("context-first-cli-mcp-workflow", "stale-agent-memory-global-summary"):
            generated_workbench = handlers.show_review(note_id)
            self.assertTrue(generated_workbench["ok"], generated_workbench)
            self.assertEqual(generated_workbench["note"]["review_state"], "reviewed")
            self.assertEqual(generated_workbench["audit_status"]["requires_audit"], False)
            self.assertEqual(generated_workbench["audit_status"]["ok"], True)

        note = handlers.get_note("reviewed-knowledge-noesis-lifecycle")
        self.assertTrue(note["ok"], note)
        self.assertEqual(note["note"]["metadata"]["type"], "reviewed-knowledge")
        self.assertIn("Noesis should represent memory as a lifecycle", note["note"]["body"])

        lineage = handlers.trace_lineage("reviewed-knowledge-noesis-lifecycle")
        self.assertTrue(lineage["ok"], lineage)
        lineage_ids = [note["noesis_id"] for note in lineage["notes"]]
        self.assertIn("source-noesis-readme", lineage_ids)
        self.assertIn("context-first-cli-mcp-workflow", lineage_ids)

        context = handlers.build_context(purpose="test context")
        self.assertTrue(context["ok"], context)
        self.assertEqual(context["content"], build_context(Vault.load(EXAMPLE_VAULT), purpose="test context"))
        self.assertIn("reviewed-knowledge-noesis-lifecycle", context["content"])
        self.assertNotIn("stale-custom-plugin-first", context["content"])

        profiled_context = handlers.build_context(scope="agent-memory", profile="review")
        self.assertTrue(profiled_context["ok"], profiled_context)
        self.assertEqual(profiled_context["profile"], "review")
        self.assertEqual(profiled_context["limit"], 6)
        self.assertEqual(profiled_context["max_chars"], 12000)
        self.assertEqual(profiled_context["applied_profile_defaults"], ["limit", "max_chars"])
        self.assertEqual(
            [note["noesis_id"] for note in profiled_context["selection"]["included"]],
            ["reviewed-knowledge-agent-memory-dogfood"],
        )
        self.assertIn(
            "reviewed-knowledge-noesis-lifecycle",
            [note["noesis_id"] for note in profiled_context["selection"]["scoped_out"]],
        )
        self.assertEqual(profiled_context["selection"]["budgeted_out"], [])
        self.assertGreaterEqual(profiled_context["selection"]["lifecycle_exclusion_summary"]["superseded"], 2)
        self.assertEqual(
            profiled_context["lineage_summaries"][0]["sources"][0]["noesis_id"],
            "source-agent-memory-session",
        )

        invalid_profile = handlers.build_context(profile="missing-profile")
        self.assertFalse(invalid_profile["ok"])
        self.assertIn("profile must be one of", invalid_profile["error"])

    def test_search_notes_filters_by_text_and_metadata(self) -> None:
        handlers = NoesisMcpHandlers(EXAMPLE_VAULT)

        result = handlers.search_notes(
            query="useful memory requires",
            note_type="claim",
            review_state="approved",
            limit=10,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["notes"][0]["noesis_id"], "claim-useful-memory-requires-lifecycle")

    def test_review_queue_rejects_invalid_mcp_filters(self) -> None:
        handlers = NoesisMcpHandlers(EXAMPLE_VAULT)

        cases = (
            ("review_state", {"review_state": "ready_for_review"}),
            ("type", {"note_type": "claimm"}),
            ("lifecycle_stage", {"lifecycle_stage": "reviewing"}),
        )
        for field, kwargs in cases:
            with self.subTest(field=field):
                result = handlers.get_review_queue(**kwargs)
                self.assertEqual(result["ok"], False)
                self.assertEqual(result["field"], field)
                self.assertIn(f"invalid {field}", result["error"])
                self.assertIsInstance(result["expected"], list)
                self.assertGreater(len(result["expected"]), 0)

    def test_review_due_on_errors_are_structured(self) -> None:
        handlers = NoesisMcpHandlers(EXAMPLE_VAULT)

        for invalid_due_on in ("not-a-date", "2026-02-31"):
            queue = handlers.get_review_queue(due_on=invalid_due_on)
            self.assertEqual(queue["ok"], False)
            self.assertEqual(queue["error"], "due_on must be YYYY-MM-DD")

        summary = handlers.get_review_summary(due_on="not-a-date")
        self.assertEqual(summary["ok"], False)
        self.assertEqual(summary["error"], "due_on must be YYYY-MM-DD")

        show = handlers.show_review("source-noesis-readme", due_on="not-a-date")
        self.assertEqual(show["ok"], False)
        self.assertEqual(show["error"], "due_on must be YYYY-MM-DD")

        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init_vault(vault_path)
            empty_handlers = NoesisMcpHandlers(vault_path)

            empty_queue = empty_handlers.get_review_queue(due_on="not-a-date")
            self.assertEqual(empty_queue["ok"], False)
            self.assertEqual(empty_queue["error"], "due_on must be YYYY-MM-DD")

    def test_review_handlers_treat_impossible_metadata_dates_as_unscheduled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "stale" / "stale-custom-plugin-first.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8").replace(
                    "next_review: 2026-06-05",
                    'next_review: "2026-02-31"',
                ),
                encoding="utf-8",
            )
            handlers = NoesisMcpHandlers(vault_path)

            lint = handlers.lint_vault()
            self.assertTrue(lint["ok"], lint)

            queue = handlers.get_review_queue()
            self.assertTrue(queue["ok"], queue)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in queue["notes"]],
            )

            summary = handlers.get_review_summary(due_on="2026-06-13")
            self.assertTrue(summary["ok"], summary)
            self.assertNotIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in summary["due_notes"]],
            )

            workbench = handlers.show_review("stale-custom-plugin-first", due_on="2026-06-13")
            self.assertTrue(workbench["ok"], workbench)
            self.assertEqual(workbench["review_due"], False)

    def test_review_handlers_normalize_metadata_datetimes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            note_path = vault_path / "stale" / "stale-custom-plugin-first.md"
            note_path.write_text(
                note_path.read_text(encoding="utf-8").replace(
                    "next_review: 2026-06-05",
                    "next_review: 2026-06-13 09:00:00",
                ),
                encoding="utf-8",
            )
            handlers = NoesisMcpHandlers(vault_path)

            lint = handlers.lint_vault()
            self.assertTrue(lint["ok"], lint)

            queue = handlers.get_review_queue(due_on="2026-06-13")
            self.assertTrue(queue["ok"], queue)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in queue["notes"]],
            )

            summary = handlers.get_review_summary(due_on="2026-06-13")
            self.assertTrue(summary["ok"], summary)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in summary["due_notes"]],
            )

            workbench = handlers.show_review("stale-custom-plugin-first", due_on="2026-06-13")
            self.assertTrue(workbench["ok"], workbench)
            self.assertEqual(workbench["review_due"], True)

    def test_review_renew_reports_latest_audit_from_relationship_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            handlers = NoesisMcpHandlers(vault_path)

            first = handlers.renew_review(
                "context-first-cli-mcp-workflow",
                next_review="2026-07-01",
                title="ZZZ Older Renewal",
                slug="older-renewal",
            )
            self.assertTrue(first["ok"], first)
            second = handlers.renew_review(
                "context-first-cli-mcp-workflow",
                next_review="2026-08-01",
                title="AAA Newer Renewal",
                slug="newer-renewal",
            )
            self.assertTrue(second["ok"], second)

            workbench = handlers.show_review("context-first-cli-mcp-workflow", due_on="2026-07-15")
            self.assertTrue(workbench["ok"], workbench)
            self.assertEqual(workbench["review_due"], False)
            self.assertEqual(workbench["review_schedule"]["next_review"], "2026-08-01")
            self.assertEqual(
                workbench["review_schedule"]["latest_audit"]["noesis_id"],
                "review-newer-renewal",
            )
            self.assertEqual(
                [audit["noesis_id"] for audit in workbench["audit_records"][-2:]],
                [
                    "review-older-renewal",
                    "review-newer-renewal",
                ],
            )

    def test_review_workbench_keeps_newer_reverse_only_audit_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            handlers = NoesisMcpHandlers(vault_path)

            linked = handlers.renew_review("context-first-cli-mcp-workflow", next_review="2026-07-01")
            self.assertTrue(linked["ok"], linked)
            (vault_path / "review" / "review-imported-later-audit.md").write_text(
                """---
title: Imported Later Audit
noesis_id: review-imported-later-audit
type: review
lifecycle_stage: review
status: complete
review_state: approved
confidence: medium
created: 2026-08-01
updated: 2026-08-01
reviewer: imported
reviewed_at: 2026-08-01
reviewed_notes:
  - "[[context-first-cli-mcp-workflow]]"
decision: renewed
next_review: 2026-09-01
tags:
  - noesis
  - review
aliases: []
---

# Imported Later Audit

## Decision

renewed

## Reviewed Note

- [[context-first-cli-mcp-workflow]]

## Basis

Imported audit record without a target-side backlink.

## Changes Requested

None.

## Next Review

2026-09-01
""",
                encoding="utf-8",
            )

            self.assertEqual(Vault.load(vault_path).validate(), [])
            workbench = handlers.show_review("context-first-cli-mcp-workflow")
            self.assertTrue(workbench["ok"], workbench)
            self.assertEqual(
                workbench["review_schedule"]["latest_audit"]["noesis_id"],
                "review-imported-later-audit",
            )
            self.assertEqual(
                [audit["noesis_id"] for audit in workbench["audit_records"][-2:]],
                [
                    "review-context-first-cli-mcp-workflow-renewed",
                    "review-imported-later-audit",
                ],
            )

    def test_invalid_vault_errors_are_structured(self) -> None:
        handlers = NoesisMcpHandlers()

        result = handlers.get_review_queue("/tmp/noesis-missing-vault")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "vault validation failed")
        self.assertEqual(result["issue_count"], 16)
        self.assertEqual(result["compatible"], False)
        self.assertEqual(result["ready_for_cli_mcp"], False)
        self.assertEqual(result["contract"]["supported"], False)
        self.assertIn("vault path does not exist", result["issues"][0]["message"])

    def test_import_source_bundle_handler_creates_evidence_and_preserves_valid_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init_vault(vault_path)
            handlers = NoesisMcpHandlers(vault_path)

            imported = handlers.import_source_bundle(
                str(CODEX_SESSION_BUNDLE),
                create_evidence=True,
            )

            self.assertTrue(imported["ok"], imported)
            self.assertEqual(imported["bundle_id"], "codex-session-export-demo")
            self.assertEqual(imported["artifact_count"], 3)
            self.assertEqual(imported["created_count"], 2)
            self.assertEqual(imported["skipped_count"], 1)
            results = imported["results"]
            self.assertEqual(results[0]["note"]["note_id"], "source-codex-session-metadata")
            self.assertEqual(results[0]["evidence_note"]["note_id"], "evidence-session-metadata")
            self.assertEqual(results[1]["note"]["note_id"], "source-codex-session-transcript")
            self.assertEqual(results[1]["evidence_note"]["note_id"], "evidence-session-transcript")
            self.assertEqual(results[2]["existing_note_id"], "source-codex-session-transcript")
            self.assertEqual(results[2]["reason"], "duplicate-content")

            vault = Vault.load(vault_path)
            self.assertEqual(vault.validate(), [])
            source = vault.find_note("source-codex-session-metadata")
            self.assertIsNotNone(source)
            assert source is not None
            self.assertEqual(source.metadata["bundle_artifact_path"], "exports/01-session.json")
            self.assertEqual(source.metadata["bundle_manifest_index"], 2)
            queue = handlers.get_review_queue()
            self.assertTrue(queue["ok"], queue)
            self.assertIn("evidence-session-metadata", [note["noesis_id"] for note in queue["notes"]])

    def test_write_workflow_creates_audited_context_and_preserves_valid_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            init_vault(vault_path)
            raw_source = tmp_path / "memory-source.md"
            raw_source.write_text(
                "# Memory Source\n\nUseful memory needs source-backed review before reuse.\n",
                encoding="utf-8",
            )
            handlers = NoesisMcpHandlers(vault_path)

            source = handlers.ingest_source(str(raw_source), "Memory Source", slug="memory-source")
            self.assertTrue(source["ok"], source)
            self.assertEqual(source["created"]["note_id"], "source-memory-source")

            evidence = handlers.create_evidence_draft(
                "source-memory-source",
                title="Source-Backed Review Evidence",
                evidence="The source says useful memory needs source-backed review before reuse.",
                slug="source-backed-review",
            )
            self.assertTrue(evidence["ok"], evidence)

            evidence_review = handlers.approve_review(
                "evidence-source-backed-review",
                reviewer="test-human",
                basis="Evidence accurately reflects the source.",
                slug="evidence-source-backed-review",
            )
            self.assertTrue(evidence_review["ok"], evidence_review)

            claim = handlers.create_claim_draft(
                ["evidence-source-backed-review"],
                title="Memory Needs Review Before Reuse",
                claim="Reusable memory should be reviewed against source-backed evidence.",
                slug="memory-needs-review-before-reuse",
            )
            self.assertTrue(claim["ok"], claim)

            claim_review = handlers.approve_review(
                "claim-memory-needs-review-before-reuse",
                reviewer="test-human",
                basis="Claim is grounded in approved evidence.",
                slug="claim-memory-needs-review-before-reuse",
            )
            self.assertTrue(claim_review["ok"], claim_review)

            synthesis = handlers.create_synthesis_draft(
                ["claim-memory-needs-review-before-reuse"],
                title="Review Before Reuse Synthesis",
                synthesis="Noesis should reuse memory only after it is grounded and reviewed.",
                slug="review-before-reuse",
            )
            self.assertTrue(synthesis["ok"], synthesis)

            synthesis_review = handlers.approve_review(
                "synthesis-review-before-reuse",
                reviewer="test-human",
                basis="Synthesis follows from the approved claim.",
                slug="synthesis-review-before-reuse",
                next_review="2026-07-06",
            )
            self.assertTrue(synthesis_review["ok"], synthesis_review)

            knowledge = handlers.promote_synthesis(
                "synthesis-review-before-reuse",
                title="Review Before Reuse Knowledge",
                knowledge="Noesis operational context should use reviewed memory, not raw drafts.",
                slug="review-before-reuse",
                next_review="2026-08-06",
            )
            self.assertTrue(knowledge["ok"], knowledge)

            context = handlers.write_context(
                purpose="prepare a future agent",
                profile="project-continuation",
                title="Review Before Reuse Context",
                slug="review-before-reuse",
                next_review="2026-08-06",
            )
            self.assertTrue(context["ok"], context)
            self.assertEqual(context["created"]["note_id"], "context-review-before-reuse")

            vault = Vault.load(vault_path)
            written_context = vault.find_note("context-review-before-reuse")
            self.assertIsNotNone(written_context)
            assert written_context is not None
            self.assertEqual(written_context.metadata["context_profile"], "project-continuation")
            self.assertEqual(written_context.metadata["context_limit"], 8)
            self.assertEqual(written_context.metadata["context_max_chars"], 16000)

            renewal = handlers.renew_review(
                "context-review-before-reuse",
                next_review="2026-09-06",
                reviewer="test-human",
                basis="Scheduled review confirms the operational context still matches current reviewed knowledge.",
                slug="context-review-before-reuse-renewal",
            )
            self.assertTrue(renewal["ok"], renewal)
            self.assertEqual(renewal["created"]["note_id"], "review-context-review-before-reuse-renewal")
            renewed_context = Vault.load(vault_path).find_note("context-review-before-reuse")
            self.assertIsNotNone(renewed_context)
            assert renewed_context is not None
            self.assertEqual(str(renewed_context.metadata["next_review"]), "2026-09-06")
            self.assertIn("[[review-context-review-before-reuse-renewal]]", renewed_context.metadata["reviewed_by"])
            workbench = handlers.show_review("context-review-before-reuse", due_on="2026-08-06")
            self.assertTrue(workbench["ok"], workbench)
            self.assertEqual(workbench["review_due"], False)
            self.assertEqual(workbench["review_schedule"]["next_review"], "2026-09-06")
            self.assertEqual(workbench["review_schedule"]["latest_audit"]["decision"], "renewed")

            self.assertEqual(Vault.load(vault_path).validate(), [])
            queue = handlers.get_review_queue()
            self.assertTrue(queue["ok"], queue)
            self.assertEqual(queue["notes"], [])

    def test_mark_stale_excludes_memory_from_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            handlers = NoesisMcpHandlers(vault_path)

            stale = handlers.mark_memory_stale(
                "reviewed-knowledge-noesis-lifecycle",
                "The lifecycle contract changed and this knowledge needs replacement.",
                superseded_by="synthesis-local-first-lifecycle-interface",
                slug="noesis-lifecycle-old",
            )

            self.assertTrue(stale["ok"], stale)
            self.assertEqual(Vault.load(vault_path).validate(), [])
            context = handlers.build_context(scope="lifecycle")
            self.assertTrue(context["ok"], context)
            self.assertIn("No current reviewed knowledge found.", context["content"])
            self.assertNotIn("Noesis should represent memory as a lifecycle", context["content"])
            context_note = (vault_path / "context" / "operational-context-first-cli-mcp-workflow.md").read_text(
                encoding="utf-8",
            )
            self.assertIn("[[stale-noesis-lifecycle-old]]", context_note)


if __name__ == "__main__":
    unittest.main()
