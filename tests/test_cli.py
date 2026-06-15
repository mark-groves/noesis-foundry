from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

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


def parse_json_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not valid JSON: {result.stdout!r}") from exc


class NoesisCliTests(unittest.TestCase):
    def test_example_vault_validates(self) -> None:
        result = run_noesis("vault", "validate", str(EXAMPLE_VAULT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validation ok", result.stdout)
        self.assertIn("notes:", result.stdout)

    def test_vault_validate_json_reports_success_and_errors(self) -> None:
        result = run_noesis("vault", "validate", str(EXAMPLE_VAULT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["vault_path"], str(EXAMPLE_VAULT.resolve()))
        self.assertGreater(payload["note_count"], 0)
        self.assertEqual(payload["issue_count"], 0)
        self.assertEqual(payload["issues"], [])
        self.assertEqual(payload["contract"]["version"], "1")
        self.assertEqual(payload["compatible"], True)
        self.assertEqual(payload["complete"], True)
        self.assertEqual(payload["ready_for_cli_mcp"], True)

        with tempfile.TemporaryDirectory() as tmp:
            missing_vault = Path(tmp) / "missing-vault"
            invalid = run_noesis("vault", "validate", str(missing_vault), "--json")
            self.assertNotEqual(invalid.returncode, 0)
            invalid_payload = parse_json_stdout(invalid)
            self.assertEqual(invalid_payload["ok"], False)
            self.assertEqual(invalid_payload["vault_path"], str(missing_vault.resolve()))
            self.assertEqual(invalid_payload["compatible"], False)
            self.assertEqual(invalid_payload["ready_for_cli_mcp"], False)
            self.assertEqual(invalid_payload["contract"]["supported"], False)
            self.assertGreater(invalid_payload["issue_count"], 0)
            self.assertIn("vault path does not exist", invalid_payload["issues"][0]["message"])

    def test_vault_doctor_reports_contract_readiness(self) -> None:
        result = run_noesis("vault", "doctor", str(EXAMPLE_VAULT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["compatible"], True)
        self.assertEqual(payload["complete"], True)
        self.assertEqual(payload["ready_for_cli_mcp"], True)
        self.assertEqual(payload["contract"]["present"], True)
        self.assertEqual(payload["contract"]["version"], "1")
        self.assertEqual(payload["issue_count"], 0)

        with tempfile.TemporaryDirectory() as tmp:
            legacy_vault = Path(tmp) / "legacy-vault"
            shutil.copytree(EXAMPLE_VAULT, legacy_vault)
            (legacy_vault / "noesis.vault.yaml").unlink()

            legacy = run_noesis("vault", "doctor", str(legacy_vault), "--json")
            self.assertNotEqual(legacy.returncode, 0)
            legacy_payload = parse_json_stdout(legacy)
            self.assertEqual(legacy_payload["compatible"], False)
            self.assertEqual(legacy_payload["ready_for_cli_mcp"], False)
            self.assertIn("missing Noesis V1 contract metadata", legacy_payload["issues"][0]["message"])

        with tempfile.TemporaryDirectory() as tmp:
            file_vault = Path(tmp) / "not-a-vault.md"
            file_vault.write_text("not a vault", encoding="utf-8")

            invalid_file = run_noesis("vault", "doctor", str(file_vault), "--json")
            self.assertNotEqual(invalid_file.returncode, 0)
            invalid_file_payload = parse_json_stdout(invalid_file)
            self.assertEqual(invalid_file_payload["compatible"], False)
            self.assertEqual(invalid_file_payload["ready_for_cli_mcp"], False)
            self.assertIn("vault path is not a directory", invalid_file_payload["issues"][0]["message"])

        with tempfile.TemporaryDirectory() as tmp:
            future_vault = Path(tmp) / "future-vault"
            shutil.copytree(EXAMPLE_VAULT, future_vault)
            contract_path = future_vault / "noesis.vault.yaml"
            contract_path.write_text(
                contract_path.read_text(encoding="utf-8").replace(
                    'requires_noesis: ">=0.1.0"',
                    'requires_noesis: ">=0.2.0"',
                ),
                encoding="utf-8",
            )

            future = run_noesis("vault", "doctor", str(future_vault), "--json")
            self.assertNotEqual(future.returncode, 0)
            future_payload = parse_json_stdout(future)
            self.assertEqual(future_payload["compatible"], False)
            self.assertEqual(future_payload["ready_for_cli_mcp"], False)
            self.assertIn("requires_noesis", future_payload["issues"][0]["message"])

        with tempfile.TemporaryDirectory() as tmp:
            incomplete_vault = Path(tmp) / "incomplete-vault"
            shutil.copytree(EXAMPLE_VAULT, incomplete_vault)
            contract_path = incomplete_vault / "noesis.vault.yaml"
            contract_path.write_text(
                contract_path.read_text(encoding="utf-8").replace(
                    'requires_noesis: ">=0.1.0"\n',
                    "",
                ),
                encoding="utf-8",
            )

            incomplete = run_noesis("vault", "doctor", str(incomplete_vault), "--json")
            self.assertNotEqual(incomplete.returncode, 0)
            incomplete_payload = parse_json_stdout(incomplete)
            self.assertEqual(incomplete_payload["compatible"], False)
            self.assertEqual(incomplete_payload["ready_for_cli_mcp"], False)
            self.assertIn("requires_noesis", incomplete_payload["issues"][0]["message"])

    def test_review_queue_json_matches_text_order(self) -> None:
        result = run_noesis("review", "queue", "--vault", str(EXAMPLE_VAULT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        expected_ids = [note.noesis_id for note in Vault.load(EXAMPLE_VAULT).review_queue()]
        actual_ids = [note["noesis_id"] for note in payload["notes"]]
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["vault_path"], str(EXAMPLE_VAULT.resolve()))
        self.assertEqual(payload["count"], len(expected_ids))
        self.assertEqual(actual_ids, expected_ids)

        with tempfile.TemporaryDirectory() as tmp:
            invalid = run_noesis("review", "queue", "--vault", str(Path(tmp) / "missing"), "--json")
            self.assertNotEqual(invalid.returncode, 0)
            invalid_payload = parse_json_stdout(invalid)
            self.assertEqual(invalid_payload["ok"], False)
            self.assertEqual(invalid_payload["error"], "vault validation failed")
            self.assertGreater(invalid_payload["issue_count"], 0)

    def test_review_queue_filters_and_summary_due_dates(self) -> None:
        due_queue = run_noesis(
            "review",
            "queue",
            "--vault",
            str(EXAMPLE_VAULT),
            "--type",
            "stale-memory",
            "--due",
            "--due-on",
            "2026-06-13",
            "--json",
        )
        self.assertEqual(due_queue.returncode, 0, due_queue.stderr)
        due_payload = parse_json_stdout(due_queue)
        self.assertEqual(due_payload["filters"]["type"], "stale-memory")
        self.assertEqual(due_payload["filters"]["due"], True)
        self.assertEqual([note["noesis_id"] for note in due_payload["notes"]], ["stale-custom-plugin-first"])

        scheduled_due_queue = run_noesis(
            "review",
            "queue",
            "--vault",
            str(EXAMPLE_VAULT),
            "--due-on",
            "2026-06-29",
            "--json",
        )
        self.assertEqual(scheduled_due_queue.returncode, 0, scheduled_due_queue.stderr)
        scheduled_due_payload = parse_json_stdout(scheduled_due_queue)
        scheduled_due_ids = [note["noesis_id"] for note in scheduled_due_payload["notes"]]
        self.assertIn("reviewed-knowledge-noesis-lifecycle", scheduled_due_ids)
        self.assertIn("context-first-cli-mcp-workflow", scheduled_due_ids)
        self.assertNotIn("review-local-first-lifecycle", scheduled_due_ids)
        self.assertNotIn("review-queue", scheduled_due_ids)

        claim_queue = run_noesis(
            "review",
            "queue",
            "--vault",
            str(EXAMPLE_VAULT),
            "--stage",
            "claim",
            "--json",
        )
        self.assertEqual(claim_queue.returncode, 0, claim_queue.stderr)
        claim_payload = parse_json_stdout(claim_queue)
        self.assertEqual([note["noesis_id"] for note in claim_payload["notes"]], ["claim-cli-authoring-loop"])

        summary = run_noesis(
            "review",
            "summary",
            "--vault",
            str(EXAMPLE_VAULT),
            "--due-on",
            "2026-06-13",
            "--json",
        )
        self.assertEqual(summary.returncode, 0, summary.stderr)
        summary_payload = parse_json_stdout(summary)
        self.assertGreaterEqual(summary_payload["pending_count"], 1)
        self.assertIn("ready-for-review", summary_payload["review_state_counts"])
        self.assertIn(
            "stale-custom-plugin-first",
            [note["noesis_id"] for note in summary_payload["due_notes"]],
        )

    def test_review_show_json_reports_support_audit_impact_and_changes(self) -> None:
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
                "Clarify the claim before it supports reviewed knowledge.",
                "--slug",
                "claim-workbench-change-request",
            )
            self.assertEqual(review.returncode, 0, review.stderr)

            show = run_noesis(
                "review",
                "show",
                "claim-useful-memory-requires-lifecycle",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            payload = parse_json_stdout(show)
            self.assertEqual(payload["ok"], True)
            self.assertEqual(payload["note"]["noesis_id"], "claim-useful-memory-requires-lifecycle")
            self.assertEqual(payload["note"]["review_state"], "changes-requested")
            self.assertIn("sources", payload["support"])
            self.assertIn("evidence", payload["support"])
            self.assertTrue(payload["audit_status"]["ok"], payload["audit_status"])
            self.assertIn(
                "reviewed-knowledge-noesis-lifecycle",
                [note["noesis_id"] for note in payload["impact"]["dependent_reviewed_knowledge"]],
            )
            self.assertIn("source-noesis-readme", [note["noesis_id"] for note in payload["lineage"]])
            self.assertIn("Clarify the claim", payload["changes_requested"][0]["changes_requested"])

    def test_review_show_reports_contexts_that_exclude_stale_memory(self) -> None:
        show = run_noesis(
            "review",
            "show",
            "stale-custom-plugin-first",
            "--vault",
            str(EXAMPLE_VAULT),
            "--json",
        )
        self.assertEqual(show.returncode, 0, show.stderr)
        payload = parse_json_stdout(show)
        self.assertIn(
            "context-first-cli-mcp-workflow",
            [note["noesis_id"] for note in payload["impact"]["dependent_contexts"]],
        )

    def test_review_renew_handles_due_stale_memory_without_reactivating_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)

            renew = run_noesis(
                "review",
                "renew",
                "stale-custom-plugin-first",
                "--vault",
                str(vault_path),
                "--reviewer",
                "test-human",
                "--basis",
                "The custom plugin assumption remains superseded by the local-first workflow.",
                "--next-review",
                "2026-07-05",
                "--slug",
                "stale-custom-plugin-still-superseded",
            )
            self.assertEqual(renew.returncode, 0, renew.stderr)
            self.assertIn("created review-stale-custom-plugin-still-superseded", renew.stdout)

            vault = Vault.load(vault_path)
            stale_note = vault.find_note("stale-custom-plugin-first")
            self.assertIsNotNone(stale_note)
            assert stale_note is not None
            self.assertEqual(stale_note.status, "superseded")
            self.assertEqual(stale_note.lifecycle_stage, "stale")
            self.assertEqual(stale_note.review_state, "reviewed")
            self.assertEqual(str(stale_note.metadata["next_review"]), "2026-07-05")
            self.assertIn("[[review-stale-custom-plugin-still-superseded]]", stale_note.metadata["reviewed_by"])

            due_queue = run_noesis(
                "review",
                "queue",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(due_queue.returncode, 0, due_queue.stderr)
            due_payload = parse_json_stdout(due_queue)
            self.assertNotIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in due_payload["notes"]],
            )

            show = run_noesis(
                "review",
                "show",
                "stale-custom-plugin-first",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            show_payload = parse_json_stdout(show)
            self.assertEqual(show_payload["review_due"], False)
            self.assertEqual(show_payload["review_schedule"]["next_review"], "2026-07-05")
            self.assertEqual(show_payload["review_schedule"]["latest_audit"]["decision"], "renewed")
            self.assertEqual(show_payload["audit_records"][-1]["noesis_id"], "review-stale-custom-plugin-still-superseded")
            self.assertIn(
                "context-first-cli-mcp-workflow",
                [note["noesis_id"] for note in show_payload["impact"]["dependent_contexts"]],
            )

            context = run_noesis(
                "context",
                "build",
                "--vault",
                str(vault_path),
                "--scope",
                "lifecycle",
                "--purpose",
                "check renewed stale memory",
            )
            self.assertEqual(context.returncode, 0, context.stderr)
            self.assertIn("reviewed-knowledge-noesis-lifecycle", context.stdout)
            self.assertNotIn("stale-custom-plugin-first", context.stdout)
            self.assertNotIn("Build Custom Obsidian Plugin First", context.stdout)

    def test_review_show_does_not_require_audits_for_generated_reviewed_notes(self) -> None:
        for note_id in ("context-first-cli-mcp-workflow", "stale-agent-memory-global-summary"):
            show = run_noesis(
                "review",
                "show",
                note_id,
                "--vault",
                str(EXAMPLE_VAULT),
                "--json",
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            payload = parse_json_stdout(show)
            self.assertEqual(payload["note"]["review_state"], "reviewed")
            self.assertEqual(payload["audit_status"]["requires_audit"], False)
            self.assertEqual(payload["audit_status"]["ok"], True)

    def test_review_queue_base_scopes_open_queue_filters_to_one_view(self) -> None:
        base = yaml.safe_load((EXAMPLE_VAULT / "_bases" / "review-queue.base").read_text(encoding="utf-8"))
        top_filters = base["filters"]["and"]
        self.assertNotIn('review_state != "approved"', top_filters)
        open_queue = next(view for view in base["views"] if view["name"] == "Open review queue")
        scheduled = next(view for view in base["views"] if view["name"] == "Due and scheduled reviews")
        self.assertIn('review_state != "approved"', open_queue["filters"]["and"])
        self.assertEqual(
            scheduled["filters"]["and"],
            ["next_review != null", 'review_state != "none"', 'type != "review"'],
        )

        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)
            initialized_base = yaml.safe_load(
                (vault_path / "_bases" / "review-queue.base").read_text(encoding="utf-8")
            )
            initialized_open_queue = next(
                view for view in initialized_base["views"] if view["name"] == "Open review queue"
            )
            initialized_scheduled = next(
                view for view in initialized_base["views"] if view["name"] == "Due and scheduled reviews"
            )
            self.assertIn('review_state != "approved"', initialized_open_queue["filters"]["and"])
            self.assertEqual(
                initialized_scheduled["filters"]["and"],
                ["next_review != null", 'review_state != "none"', 'type != "review"'],
            )

    def test_review_due_on_rejects_invalid_values(self) -> None:
        for invalid_due_on in ("not-a-date", "2026-02-31"):
            queue = run_noesis(
                "review",
                "queue",
                "--vault",
                str(EXAMPLE_VAULT),
                "--due-on",
                invalid_due_on,
                "--json",
            )
            self.assertNotEqual(queue.returncode, 0)
            queue_payload = parse_json_stdout(queue)
            self.assertEqual(queue_payload["ok"], False)
            self.assertEqual(queue_payload["error"], "due_on must be YYYY-MM-DD")

        summary = run_noesis(
            "review",
            "summary",
            "--vault",
            str(EXAMPLE_VAULT),
            "--due-on",
            "not-a-date",
        )
        self.assertNotEqual(summary.returncode, 0)
        self.assertIn("ERROR due_on must be YYYY-MM-DD", summary.stderr)

        show = run_noesis(
            "review",
            "show",
            "source-noesis-readme",
            "--vault",
            str(EXAMPLE_VAULT),
            "--due-on",
            "not-a-date",
            "--json",
        )
        self.assertNotEqual(show.returncode, 0)
        show_payload = parse_json_stdout(show)
        self.assertEqual(show_payload["ok"], False)
        self.assertEqual(show_payload["error"], "due_on must be YYYY-MM-DD")

        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)

            empty_queue = run_noesis(
                "review",
                "queue",
                "--vault",
                str(vault_path),
                "--due-on",
                "not-a-date",
                "--json",
            )
            self.assertNotEqual(empty_queue.returncode, 0)
            empty_payload = parse_json_stdout(empty_queue)
            self.assertEqual(empty_payload["ok"], False)
            self.assertEqual(empty_payload["error"], "due_on must be YYYY-MM-DD")

    def test_review_workbench_treats_impossible_metadata_dates_as_unscheduled(self) -> None:
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

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            queue = run_noesis("review", "queue", "--vault", str(vault_path), "--json")
            self.assertEqual(queue.returncode, 0, queue.stderr)
            queue_payload = parse_json_stdout(queue)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in queue_payload["notes"]],
            )

            summary = run_noesis(
                "review",
                "summary",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_payload = parse_json_stdout(summary)
            self.assertNotIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in summary_payload["due_notes"]],
            )

            show = run_noesis(
                "review",
                "show",
                "stale-custom-plugin-first",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            show_payload = parse_json_stdout(show)
            self.assertEqual(show_payload["review_due"], False)

    def test_review_workbench_normalizes_metadata_datetimes(self) -> None:
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

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            queue = run_noesis(
                "review",
                "queue",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(queue.returncode, 0, queue.stderr)
            queue_payload = parse_json_stdout(queue)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in queue_payload["notes"]],
            )

            summary = run_noesis(
                "review",
                "summary",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(summary.returncode, 0, summary.stderr)
            summary_payload = parse_json_stdout(summary)
            self.assertIn(
                "stale-custom-plugin-first",
                [note["noesis_id"] for note in summary_payload["due_notes"]],
            )

            show = run_noesis(
                "review",
                "show",
                "stale-custom-plugin-first",
                "--vault",
                str(vault_path),
                "--due-on",
                "2026-06-13",
                "--json",
            )
            self.assertEqual(show.returncode, 0, show.stderr)
            show_payload = parse_json_stdout(show)
            self.assertEqual(show_payload["review_due"], True)

    def test_example_agent_memory_dogfood_context_uses_reviewed_knowledge(self) -> None:
        context = run_noesis(
            "context",
            "build",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
            "--purpose",
            "prepare a future agent",
        )
        self.assertEqual(context.returncode, 0, context.stderr)
        self.assertIn("reviewed-knowledge-agent-memory-dogfood", context.stdout)
        self.assertIn("Agents should turn session artifacts into reviewed Noesis memory", context.stdout)
        self.assertNotIn("Agents can safely copy global summary snippets", context.stdout)
        self.assertNotIn("stale-agent-memory-global-summary", context.stdout)

        context_note = (
            EXAMPLE_VAULT / "context" / "operational-context-agent-memory-dogfood.md"
        ).read_text(encoding="utf-8")
        self.assertIn("[[reviewed-knowledge-agent-memory-dogfood]]", context_note)
        self.assertIn("[[stale-agent-memory-global-summary]]", context_note)

        trace = run_noesis("trace", "context-agent-memory-dogfood", "--vault", str(EXAMPLE_VAULT))
        self.assertEqual(trace.returncode, 0, trace.stderr)
        for expected in (
            "source-agent-memory-session",
            "evidence-agent-memory-dogfood",
            "claim-agent-memory-dogfood",
            "review-agent-memory-dogfood",
            "synthesis-agent-memory-dogfood",
            "reviewed-knowledge-agent-memory-dogfood",
            "context-agent-memory-dogfood",
            "stale-agent-memory-global-summary",
        ):
            self.assertIn(expected, trace.stdout)

    def test_context_explain_json_reports_profile_provenance_and_lineage(self) -> None:
        scoped = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
            "--purpose",
            "continue Noesis Foundry project work",
            "--profile",
            "review",
            "--json",
        )
        self.assertEqual(scoped.returncode, 0, scoped.stderr)
        scoped_payload = parse_json_stdout(scoped)
        self.assertEqual(scoped_payload["profile"], "review")
        self.assertEqual(scoped_payload["limit"], 6)
        self.assertEqual(scoped_payload["max_chars"], 12000)
        self.assertEqual(scoped_payload["requested_limit"], None)
        self.assertEqual(scoped_payload["requested_max_chars"], None)
        self.assertEqual(scoped_payload["applied_profile_defaults"], ["limit", "max_chars"])

        selection = scoped_payload["selection"]
        self.assertEqual(
            [note["noesis_id"] for note in selection["included"]],
            ["reviewed-knowledge-agent-memory-dogfood"],
        )
        self.assertIn(
            "reviewed-knowledge-noesis-lifecycle",
            [note["noesis_id"] for note in selection["scoped_out"]],
        )
        self.assertEqual(selection["budgeted_out"], [])
        self.assertIn("profile 'review' supplied context defaults", selection["included"][0]["selection_reason"])
        self.assertIn("profile 'review' supplied context defaults", selection["scoped_out"][0]["selection_reason"])
        self.assertGreaterEqual(selection["lifecycle_exclusion_summary"]["superseded"], 2)
        self.assertGreaterEqual(selection["lifecycle_exclusion_summary"]["archived"], 1)
        self.assertIn(
            "stale-agent-memory-global-summary",
            [note["noesis_id"] for note in selection["lifecycle_excluded"]],
        )
        self.assertIn(
            "archive-2026-05-29-first-lifecycle",
            [note["noesis_id"] for note in selection["lifecycle_excluded"]],
        )

        lineage = scoped_payload["lineage_summaries"][0]
        self.assertEqual(lineage["reviewed_knowledge"]["noesis_id"], "reviewed-knowledge-agent-memory-dogfood")
        self.assertEqual(lineage["counts"]["sources"], 1)
        self.assertEqual(lineage["counts"]["evidence"], 1)
        self.assertEqual(lineage["counts"]["claims"], 1)
        self.assertEqual(lineage["counts"]["syntheses"], 1)
        self.assertEqual(lineage["counts"]["reviews"], 1)
        self.assertEqual(lineage["sources"][0]["noesis_id"], "source-agent-memory-session")

        overridden = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
            "--profile",
            "review",
            "--limit",
            "2",
            "--max-chars",
            "5000",
            "--json",
        )
        self.assertEqual(overridden.returncode, 0, overridden.stderr)
        overridden_payload = parse_json_stdout(overridden)
        self.assertEqual(overridden_payload["profile"], "review")
        self.assertEqual(overridden_payload["limit"], 2)
        self.assertEqual(overridden_payload["max_chars"], 5000)
        self.assertEqual(overridden_payload["requested_limit"], 2)
        self.assertEqual(overridden_payload["requested_max_chars"], 5000)
        self.assertEqual(overridden_payload["applied_profile_defaults"], [])
        overridden_selection = overridden_payload["selection"]
        for selection_group in ("included", "scoped_out"):
            reason = overridden_selection[selection_group][0]["selection_reason"]
            self.assertIn("profile 'review' selected with explicit context budgets", reason)
            self.assertNotIn("supplied context defaults", reason)

        budgeted = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--limit",
            "1",
            "--json",
        )
        self.assertEqual(budgeted.returncode, 0, budgeted.stderr)
        budgeted_payload = parse_json_stdout(budgeted)
        self.assertEqual(budgeted_payload["reviewed_knowledge_count"], 1)
        self.assertGreaterEqual(len(budgeted_payload["selection"]["budgeted_out"]), 1)
        self.assertIn(
            "excluded by limit 1",
            budgeted_payload["selection"]["budgeted_out"][0]["selection_reason"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            stale_note_path = vault_path / "stale" / "stale-agent-memory-global-summary.md"
            stale_note_path.write_text(
                stale_note_path.read_text(encoding="utf-8").replace(
                    "status: superseded",
                    "status: stale",
                    1,
                ),
                encoding="utf-8",
            )

            stale = run_noesis("context", "explain", "--vault", str(vault_path), "--json")
            self.assertEqual(stale.returncode, 0, stale.stderr)
            stale_payload = parse_json_stdout(stale)
            stale_summary = stale_payload["selection"]["lifecycle_exclusion_summary"]
            self.assertGreaterEqual(stale_summary["stale"], 1)
            self.assertGreaterEqual(stale_summary["superseded"], 1)
            self.assertGreaterEqual(stale_summary["archived"], 1)

        text = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
            "--profile",
            "review",
        )
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("Profile: review", text.stdout)
        self.assertIn("## Included Lineage Summaries", text.stdout)
        self.assertIn("## Scoped Out", text.stdout)
        self.assertIn("## Budgeted Out", text.stdout)
        self.assertIn("Summary: stale=0, superseded=", text.stdout)

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
            self.assertTrue((vault_path / "noesis.vault.yaml").exists())

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

    def test_directory_ingest_sorts_sources_skips_duplicates_and_creates_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            vault_path = tmp_path / "vault"
            import_path = tmp_path / "imports"
            nested_path = import_path / "nested"
            nested_path.mkdir(parents=True)
            alpha = import_path / "alpha-note.md"
            beta = import_path / "beta-note.md"
            beta_duplicate = nested_path / "beta-copy.txt"
            alpha.write_text("# Alpha\n\nfirst source\n", encoding="utf-8")
            beta.write_text("# Beta\n\nduplicate source\n", encoding="utf-8")
            beta_duplicate.write_text("# Beta\n\nduplicate source\n", encoding="utf-8")

            init = run_noesis("vault", "init", str(vault_path))
            self.assertEqual(init.returncode, 0, init.stderr)

            ingest = run_noesis(
                "ingest",
                "source",
                "--vault",
                str(vault_path),
                "--directory",
                str(import_path),
                "--recursive",
                "--pattern",
                "*.md",
                "--pattern",
                "*.txt",
                "--source-type",
                "project-document",
                "--author",
                "Noesis Test",
                "--evidence-drafts",
                "--json",
            )
            self.assertEqual(ingest.returncode, 0, ingest.stderr)
            payload = parse_json_stdout(ingest)
            self.assertEqual(payload["created_count"], 2)
            self.assertEqual(payload["skipped_count"], 1)
            results = payload["results"]
            self.assertEqual([result["source_file"] for result in results], [str(alpha), str(beta), str(beta_duplicate)])
            self.assertEqual(results[0]["note_id"], "source-alpha-note")
            self.assertEqual(results[1]["note_id"], "source-beta-note")
            self.assertEqual(results[2]["status"], "skipped")
            self.assertEqual(results[2]["reason"], "duplicate-content")
            self.assertEqual(results[2]["existing_note_id"], "source-beta-note")
            self.assertEqual(results[0]["evidence_note_id"], "evidence-evidence-from-alpha-note")
            self.assertEqual(results[1]["evidence_note_id"], "evidence-evidence-from-beta-note")

            vault = Vault.load(vault_path)
            alpha_note = vault.find_note("source-alpha-note")
            self.assertIsNotNone(alpha_note)
            assert alpha_note is not None
            self.assertEqual(alpha_note.metadata["source_type"], "project-document")
            self.assertEqual(alpha_note.metadata["author"], "Noesis Test")
            self.assertEqual(alpha_note.metadata["original_url"], "unknown")
            self.assertEqual(alpha_note.metadata["source_date"], "unknown")
            self.assertEqual(alpha_note.metadata["source_size_bytes"], alpha.stat().st_size)
            self.assertEqual(alpha_note.metadata["original_path"], str(alpha))
            self.assertTrue(str(alpha_note.metadata["content_hash"]).startswith("sha256:"))
            self.assertTrue((vault_path / "raw" / "alpha-note.md").exists())
            self.assertTrue((vault_path / "raw" / "beta-note.md").exists())
            self.assertFalse((vault_path / "raw" / "beta-copy.txt").exists())

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_trace_json_reports_lineage_and_missing_note_errors(self) -> None:
        result = run_noesis(
            "trace",
            "reviewed-knowledge-noesis-lifecycle",
            "--vault",
            str(EXAMPLE_VAULT),
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        lineage_ids = [note["noesis_id"] for note in payload["notes"]]
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["vault_path"], str(EXAMPLE_VAULT.resolve()))
        self.assertEqual(payload["note"], "reviewed-knowledge-noesis-lifecycle")
        self.assertIn("source-noesis-readme", lineage_ids)
        self.assertIn("reviewed-knowledge-noesis-lifecycle", lineage_ids)
        self.assertEqual(payload["count"], len(lineage_ids))

        missing = run_noesis("trace", "missing-note", "--vault", str(EXAMPLE_VAULT), "--json")
        self.assertNotEqual(missing.returncode, 0)
        missing_payload = parse_json_stdout(missing)
        self.assertEqual(missing_payload["ok"], False)
        self.assertEqual(missing_payload["note"], "missing-note")
        self.assertIn("note not found or no lineage", missing_payload["error"])

    def test_trace_json_returns_lineage_despite_unrelated_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            (vault_path / "sources" / "source-unrelated-broken-link.md").write_text(
                """---
title: Unrelated Broken Link
noesis_id: source-unrelated-broken-link
type: source
lifecycle_stage: source
status: captured
review_state: reviewed
confidence: medium
created: 2026-06-13
updated: 2026-06-13
sources:
  - "[[missing-unrelated-note]]"
---

# Unrelated Broken Link
""",
                encoding="utf-8",
            )

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertNotEqual(validate.returncode, 0)
            self.assertIn("missing-unrelated-note", validate.stderr)

            result = run_noesis(
                "trace",
                "reviewed-knowledge-noesis-lifecycle",
                "--vault",
                str(vault_path),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = parse_json_stdout(result)
            lineage_ids = [note["noesis_id"] for note in payload["notes"]]
            self.assertEqual(payload["ok"], True)
            self.assertIn("source-noesis-readme", lineage_ids)
            self.assertIn("reviewed-knowledge-noesis-lifecycle", lineage_ids)

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

    def test_context_build_json_returns_context_payload(self) -> None:
        result = run_noesis(
            "context",
            "build",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "lifecycle",
            "--purpose",
            "prepare an agent",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        knowledge_ids = [note["noesis_id"] for note in payload["reviewed_knowledge"]]
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["vault_path"], str(EXAMPLE_VAULT.resolve()))
        self.assertEqual(payload["scope"], "lifecycle")
        self.assertEqual(payload["purpose"], "prepare an agent")
        self.assertEqual(payload["reviewed_knowledge_count"], len(knowledge_ids))
        self.assertIn("reviewed-knowledge-noesis-lifecycle", knowledge_ids)
        self.assertIn("Purpose: prepare an agent", payload["content"])
        self.assertIn("reviewed-knowledge-noesis-lifecycle", payload["content"])
        self.assertEqual(payload["available_reviewed_knowledge_count"], 2)
        self.assertEqual(payload["selection"]["included"][0]["selection_status"], "included")

        with tempfile.TemporaryDirectory() as tmp:
            invalid = run_noesis("context", "build", "--vault", str(Path(tmp) / "missing"), "--json")
            self.assertNotEqual(invalid.returncode, 0)
            invalid_payload = parse_json_stdout(invalid)
            self.assertEqual(invalid_payload["ok"], False)
            self.assertEqual(invalid_payload["error"], "vault validation failed")
            self.assertGreater(invalid_payload["issue_count"], 0)

    def test_context_build_limit_reports_budgeted_provenance(self) -> None:
        result = run_noesis(
            "context",
            "build",
            "--vault",
            str(EXAMPLE_VAULT),
            "--purpose",
            "brief a constrained agent",
            "--limit",
            "1",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        included_ids = [note["noesis_id"] for note in payload["selection"]["included"]]
        excluded = payload["selection"]["excluded"]
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["reviewed_knowledge_count"], 1)
        self.assertEqual(included_ids, ["reviewed-knowledge-agent-memory-dogfood"])
        self.assertEqual(excluded[0]["noesis_id"], "reviewed-knowledge-noesis-lifecycle")
        self.assertEqual(excluded[0]["selection_status"], "budgeted_out")
        self.assertIn("excluded by limit 1", excluded[0]["selection_reason"])
        self.assertNotIn("Noesis should represent memory as a lifecycle", payload["content"])

    def test_context_build_max_chars_excludes_first_over_budget_note(self) -> None:
        result = run_noesis(
            "context",
            "build",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "noesis",
            "--limit",
            "1",
            "--max-chars",
            "1",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        excluded_ids = [note["noesis_id"] for note in payload["selection"]["excluded"]]
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["reviewed_knowledge_count"], 0)
        self.assertEqual(payload["selection"]["included"], [])
        self.assertIn("reviewed-knowledge-agent-memory-dogfood", excluded_ids)
        self.assertIn("reviewed-knowledge-noesis-lifecycle", excluded_ids)
        for note in payload["selection"]["excluded"]:
            self.assertEqual(note["selection_status"], "budgeted_out")
            self.assertIn("excluded by max_chars 1", note["selection_reason"])
            self.assertGreater(note["content_chars"], payload["max_chars"])
        self.assertIn("No current reviewed knowledge found.", payload["content"])
        self.assertNotIn("Agents should turn session artifacts", payload["content"])
        self.assertNotIn("Noesis should represent memory as a lifecycle", payload["content"])

    def test_context_explain_reports_scoped_and_lifecycle_exclusions(self) -> None:
        result = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
            "--purpose",
            "prepare a future agent",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = parse_json_stdout(result)
        included_ids = [note["noesis_id"] for note in payload["selection"]["included"]]
        scoped_out_ids = [note["noesis_id"] for note in payload["selection"]["excluded"]]
        lifecycle_excluded_ids = [
            note["noesis_id"] for note in payload["selection"]["lifecycle_excluded"]
        ]
        self.assertEqual(included_ids, ["reviewed-knowledge-agent-memory-dogfood"])
        self.assertIn("reviewed-knowledge-noesis-lifecycle", scoped_out_ids)
        self.assertIn("stale-agent-memory-global-summary", lifecycle_excluded_ids)

        text = run_noesis(
            "context",
            "explain",
            "--vault",
            str(EXAMPLE_VAULT),
            "--scope",
            "agent-memory",
        )
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("Lifecycle-excluded notes are background provenance only.", text.stdout)
        self.assertIn("stale-agent-memory-global-summary", text.stdout)
        self.assertNotIn("Agents can safely copy global summary snippets", text.stdout)

    def test_context_explain_reports_archived_history_as_lifecycle_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "vault"
            shutil.copytree(EXAMPLE_VAULT, vault_path)
            archived_note = vault_path / "archive" / "history" / "archived-context-note.md"
            archived_note.write_text(
                """---
title: Archived Context Note
noesis_id: archived-context-note
type: archived-history
lifecycle_stage: archive
status: archived
review_state: reviewed
confidence: medium
created: 2026-06-13
updated: 2026-06-13
tags:
  - noesis
  - archive
aliases: []
---

# Archived Context Note

This archived note is provenance, not active guidance.
""",
                encoding="utf-8",
            )

            validate = run_noesis("vault", "validate", str(vault_path))
            self.assertEqual(validate.returncode, 0, validate.stderr)

            result = run_noesis("context", "explain", "--vault", str(vault_path), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = parse_json_stdout(result)
            lifecycle_excluded = payload["selection"]["lifecycle_excluded"]
            archived = [
                note for note in lifecycle_excluded if note["noesis_id"] == "archived-context-note"
            ]
            self.assertEqual(len(archived), 1)
            self.assertEqual(archived[0]["selection_status"], "lifecycle_excluded")
            self.assertIn("archived-history has status 'archived'", archived[0]["selection_reason"])

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

            context = run_noesis(
                "context",
                "build",
                "--vault",
                str(vault_path),
                "--scope",
                "lifecycle",
            )
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

            context = run_noesis(
                "context",
                "build",
                "--vault",
                str(vault_path),
                "--scope",
                "lifecycle",
            )
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

            context = run_noesis(
                "context",
                "build",
                "--vault",
                str(vault_path),
                "--scope",
                "lifecycle",
            )
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
