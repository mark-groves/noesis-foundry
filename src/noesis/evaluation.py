"""Small, reproducible quality evaluations for Noesis."""

from __future__ import annotations

from typing import Any

from .retrieval import rank_notes
from .vault import Vault, compose_context


def evaluate_retrieval(vault: Vault, specification: dict[str, Any]) -> dict[str, Any]:
    queries = specification.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("retrieval evaluation requires a non-empty queries list")
    default_k = positive_int(specification.get("recall_at", 5), "recall_at")
    results: list[dict[str, Any]] = []
    reciprocal_rank_total = 0.0
    recall_total = 0.0
    for index, item in enumerate(queries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"retrieval query {index} must be a mapping")
        query = required_text(item, "query", index)
        relevant = item.get("relevant")
        if not isinstance(relevant, list) or not relevant or any(not str(value).strip() for value in relevant):
            raise ValueError(f"retrieval query {index} requires a non-empty relevant list")
        relevant_ids = {str(value) for value in relevant}
        filters = item.get("filters") or {}
        if not isinstance(filters, dict):
            raise ValueError(f"retrieval query {index} filters must be a mapping")
        candidates = [note for note in vault.notes if note_matches_filters(note, filters)]
        hits = rank_notes(candidates, query)
        ranked_ids = [hit.note.noesis_id for hit in hits]
        first_rank = next((rank for rank, note_id in enumerate(ranked_ids, start=1) if note_id in relevant_ids), None)
        reciprocal_rank = 1.0 / first_rank if first_rank is not None else 0.0
        k = positive_int(item.get("recall_at", default_k), f"query {index} recall_at")
        recall = len(relevant_ids.intersection(ranked_ids[:k])) / len(relevant_ids)
        reciprocal_rank_total += reciprocal_rank
        recall_total += recall
        results.append(
            {
                "id": str(item.get("id") or f"query-{index}"),
                "query": query,
                "filters": filters,
                "relevant": sorted(relevant_ids),
                "top_ids": ranked_ids[:k],
                "first_relevant_rank": first_rank,
                "reciprocal_rank": round(reciprocal_rank, 6),
                "recall_at": k,
                "recall": round(recall, 6),
            }
        )
    count = len(results)
    return {
        "query_count": count,
        "mean_reciprocal_rank": round(reciprocal_rank_total / count, 6),
        "mean_recall": round(recall_total / count, 6),
        "results": results,
    }


def note_matches_filters(note: Any, filters: dict[str, Any]) -> bool:
    mappings = {
        "type": getattr(note, "type", ""),
        "lifecycle_stage": getattr(note, "lifecycle_stage", ""),
        "status": getattr(note, "status", ""),
        "review_state": getattr(note, "review_state", ""),
    }
    return all(key not in filters or str(filters[key]) == value for key, value in mappings.items())


def required_text(item: dict[str, Any], key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"retrieval query {index} requires non-empty {key}")
    return value.strip()


def positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def evaluate_context_dogfood(vault: Vault, specification: dict[str, Any]) -> dict[str, Any]:
    scenarios = specification.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("context dogfood evaluation requires a non-empty scenarios list")
    baseline_chars = sum(len(note.body.strip()) for note in vault.notes)
    results: list[dict[str, Any]] = []
    for index, item in enumerate(scenarios, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"context scenario {index} must be a mapping")
        scope = required_text(item, "scope", index)
        expected_top = required_text(item, "expected_top", index)
        as_of = str(item.get("as_of") or "").strip()
        if not as_of:
            raise ValueError(f"context scenario {index} requires non-empty as_of")
        forbidden = {str(value) for value in item.get("forbidden_active", [])}
        package = compose_context(
            vault,
            scope=scope,
            purpose=str(item.get("purpose") or "Continue work from reviewed knowledge."),
            limit=positive_int(item.get("limit", 1), f"context scenario {index} limit"),
            max_chars=item.get("max_chars"),
            profile=item.get("profile"),
            as_of=as_of,
            freshness_policy=str(item.get("freshness_policy") or "strict"),
        )
        active_ids = [selection.note.noesis_id for selection in package.included]
        leaked_ids = sorted(forbidden.intersection(active_ids))
        selected_top = active_ids[0] if active_ids else None
        provenance_complete = (
            len(package.input_hashes) == len(package.included)
            and len(package.lineage_summaries) == len(package.included)
            and all(summary.sources and summary.evidence and summary.claims and summary.syntheses and summary.reviews for summary in package.lineage_summaries)
        )
        context_chars = len(package.content)
        compression_ratio = 1.0 - (context_chars / baseline_chars) if baseline_chars else 0.0
        passed = selected_top == expected_top and not leaked_ids and provenance_complete
        results.append(
            {
                "id": str(item.get("id") or f"scenario-{index}"),
                "scope": scope,
                "as_of": package.as_of,
                "freshness_policy": package.freshness_policy,
                "expected_top": expected_top,
                "selected_top": selected_top,
                "active_ids": active_ids,
                "forbidden_active_leaks": leaked_ids,
                "provenance_complete": provenance_complete,
                "context_chars": context_chars,
                "baseline_vault_body_chars": baseline_chars,
                "compression_ratio": round(compression_ratio, 6),
                "passed": passed,
            }
        )
    count = len(results)
    return {
        "scenario_count": count,
        "scenario_pass_rate": round(sum(1 for result in results if result["passed"]) / count, 6),
        "forbidden_active_leak_count": sum(len(result["forbidden_active_leaks"]) for result in results),
        "provenance_complete_rate": round(
            sum(1 for result in results if result["provenance_complete"]) / count,
            6,
        ),
        "mean_compression_ratio": round(sum(result["compression_ratio"] for result in results) / count, 6),
        "results": results,
    }
