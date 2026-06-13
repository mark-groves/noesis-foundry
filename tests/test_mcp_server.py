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
                "noesis_ingest_source",
                "noesis_lint_vault",
                "noesis_mark_memory_stale",
                "noesis_promote_synthesis",
                "noesis_request_review_changes",
                "noesis_search_notes",
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

    def test_invalid_vault_errors_are_structured(self) -> None:
        handlers = NoesisMcpHandlers()

        result = handlers.get_review_queue("/tmp/noesis-missing-vault")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "vault validation failed")
        self.assertEqual(result["issue_count"], 15)
        self.assertIn("vault path does not exist", result["issues"][0]["message"])

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
                title="Review Before Reuse Context",
                slug="review-before-reuse",
                next_review="2026-08-06",
            )
            self.assertTrue(context["ok"], context)
            self.assertEqual(context["created"]["note_id"], "context-review-before-reuse")

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
