#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ruff check src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/run_retrieval_eval.py
PYTHONPATH=src python scripts/run_dogfood_eval.py
PYTHONPATH=src python -m noesis vault validate examples/noesis-vault
git diff --check
