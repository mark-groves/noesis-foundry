#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from noesis.evaluation import evaluate_retrieval  # noqa: E402
from noesis.vault import Vault  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the checked-in Noesis retrieval evaluation corpus.")
    parser.add_argument("spec", nargs="?", type=Path, default=ROOT / "evals" / "retrieval-v1.yaml")
    parser.add_argument("--min-mrr", type=float, default=0.9)
    parser.add_argument("--min-recall", type=float, default=0.9)
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    specification = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    vault_path = Path(str(specification.get("vault", "examples/noesis-vault")))
    if not vault_path.is_absolute():
        vault_path = ROOT / vault_path
    vault = Vault.load(vault_path)
    issues = vault.validate()
    if issues:
        payload = {
            "ok": False,
            "error": "vault validation failed",
            "issues": [issue.format(vault.root) for issue in issues],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    metrics = evaluate_retrieval(vault, specification)
    passed = (
        metrics["mean_reciprocal_rank"] >= args.min_mrr
        and metrics["mean_recall"] >= args.min_recall
    )
    print(
        json.dumps(
            {
                "ok": passed,
                "spec": str(spec_path),
                "vault": str(vault.root),
                "thresholds": {"min_mrr": args.min_mrr, "min_recall": args.min_recall},
                **metrics,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
