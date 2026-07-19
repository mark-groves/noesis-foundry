from __future__ import annotations

from pathlib import Path
import unittest

import yaml

from noesis.evaluation import evaluate_context_dogfood
from noesis.vault import Vault


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_VAULT = ROOT / "examples" / "noesis-vault"


class DogfoodEvaluationTests(unittest.TestCase):
    def test_context_scenario_requires_forbidden_active_list(self) -> None:
        specification = {
            "scenarios": [
                {
                    "scope": "agent-memory",
                    "expected_top": "reviewed-knowledge-agent-memory-dogfood",
                    "as_of": "2026-06-13",
                    "forbidden_active": "stale-agent-memory-global-summary",
                }
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            "context scenario 1 forbidden_active must be a list",
        ):
            evaluate_context_dogfood(Vault.load(EXAMPLE_VAULT), specification)

    def test_checked_in_context_scenarios_meet_outcome_gate(self) -> None:
        specification = yaml.safe_load(
            (ROOT / "evals" / "context-dogfood-v1.yaml").read_text(encoding="utf-8")
        )
        metrics = evaluate_context_dogfood(Vault.load(EXAMPLE_VAULT), specification)
        self.assertEqual(metrics["scenario_pass_rate"], 1.0)
        self.assertEqual(metrics["forbidden_active_leak_count"], 0)
        self.assertEqual(metrics["provenance_complete_rate"], 1.0)
        self.assertGreaterEqual(metrics["mean_compression_ratio"], 0.8)
