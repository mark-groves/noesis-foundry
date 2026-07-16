from __future__ import annotations

from pathlib import Path
import unittest

import yaml

from noesis.evaluation import evaluate_retrieval
from noesis.retrieval import rank_notes
from noesis.vault import Note, Vault


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


def note(note_id: str, title: str, body: str) -> Note:
    path = Path(f"knowledge/{note_id}.md")
    return Note(
        path=path,
        rel_path=path,
        metadata={"noesis_id": note_id, "title": title, "tags": []},
        body=body,
    )


class RetrievalTests(unittest.TestCase):
    def test_ranker_prefers_title_and_does_not_use_substrings(self) -> None:
        title_match = note("agent-handoff", "Agent Handoff", "Short current guidance.")
        body_match = note("other", "Other Note", "An agent handoff is mentioned in the body.")
        substring_only = note("management", "Management", "Budget planning.")

        hits = rank_notes([body_match, substring_only, title_match], "agent handoff")
        self.assertEqual([hit.note.noesis_id for hit in hits], ["agent-handoff", "other"])
        self.assertNotIn("management", [hit.note.noesis_id for hit in rank_notes([substring_only], "agent")])

    def test_checked_in_retrieval_corpus_meets_quality_gate(self) -> None:
        specification = yaml.safe_load((ROOT / "evals" / "retrieval-v1.yaml").read_text(encoding="utf-8"))
        metrics = evaluate_retrieval(Vault.load(EXAMPLE_VAULT), specification)
        self.assertGreaterEqual(metrics["mean_reciprocal_rank"], 0.9)
        self.assertGreaterEqual(metrics["mean_recall"], 0.9)
