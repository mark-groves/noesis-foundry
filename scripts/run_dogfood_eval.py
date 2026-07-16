#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from noesis.evaluation import evaluate_context_dogfood  # noqa: E402
from noesis.vault import Vault  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the checked-in Noesis context dogfood benchmark.")
    parser.add_argument("spec", nargs="?", type=Path, default=ROOT / "evals" / "context-dogfood-v1.yaml")
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    specification = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    vault_path = Path(str(specification.get("vault", "examples/noesis-vault")))
    if not vault_path.is_absolute():
        vault_path = ROOT / vault_path
    vault = Vault.load(vault_path)
    issues = vault.validate()
    if issues:
        print(
            json.dumps(
                {"ok": False, "error": "vault validation failed", "issues": [issue.format(vault.root) for issue in issues]},
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    metrics = evaluate_context_dogfood(vault, specification)
    thresholds = specification.get("thresholds") or {}
    passed = (
        metrics["scenario_pass_rate"] >= float(thresholds.get("min_scenario_pass_rate", 1.0))
        and metrics["forbidden_active_leak_count"] <= int(thresholds.get("max_forbidden_active_leaks", 0))
        and metrics["provenance_complete_rate"] >= float(thresholds.get("min_provenance_complete_rate", 1.0))
        and metrics["mean_compression_ratio"] >= float(thresholds.get("min_mean_compression_ratio", 0.8))
    )
    print(
        json.dumps(
            {
                "ok": passed,
                "spec": str(spec_path),
                "vault": str(vault.root),
                "thresholds": thresholds,
                **metrics,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
