"""Deterministic, dependency-free relevance ranking for Noesis notes."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable, Sequence


TOKEN_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?")


@dataclass(frozen=True)
class RetrievalHit:
    note: Any
    score: float
    matched_terms: tuple[str, ...]


def tokenize(value: Any) -> list[str]:
    return TOKEN_RE.findall(str(value).casefold())


def index_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    for token in tokenize(value):
        tokens.append(token)
        if "-" in token:
            tokens.extend(part for part in token.split("-") if part)
    return tokens


def rank_notes(notes: Sequence[Any], query: str | None) -> list[RetrievalHit]:
    """Rank notes using field-aware BM25-style lexical relevance.

    The ranker intentionally stays local and deterministic. Exact tokens in a
    title, identifier, alias, tag, or path carry more weight than body matches;
    exact title phrases receive an additional boost.
    """

    phrase_terms = tuple(tokenize(query or ""))
    query_terms = tuple(dict.fromkeys(phrase_terms))
    if not query_terms:
        return [RetrievalHit(note, 0.0, ()) for note in sorted(notes, key=note_sort_key)]

    documents = [note_weighted_terms(note) for note in notes]
    document_frequency = {
        term: sum(1 for document in documents if term in document)
        for term in query_terms
    }
    document_count = max(len(notes), 1)
    hits: list[RetrievalHit] = []
    for note, weighted_terms in zip(notes, documents, strict=True):
        matched = tuple(term for term in query_terms if term in weighted_terms)
        if not matched:
            continue
        score = 0.0
        for term in matched:
            frequency = weighted_terms[term]
            inverse_document_frequency = math.log(
                1.0 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            score += inverse_document_frequency * (frequency * 2.2) / (frequency + 1.2)
        title_tokens = tokenize(getattr(note, "title", ""))
        phrase_length = len(phrase_terms)
        if phrase_terms and any(
            tuple(title_tokens[index : index + phrase_length]) == phrase_terms
            for index in range(len(title_tokens) - phrase_length + 1)
        ):
            score += 3.0
        if len(matched) == len(query_terms):
            score += 1.5
        hits.append(RetrievalHit(note, round(score, 6), matched))
    return sorted(hits, key=lambda hit: (-hit.score, note_sort_key(hit.note)))


def note_weighted_terms(note: Any) -> dict[str, float]:
    metadata = getattr(note, "metadata", {})
    fields: Iterable[tuple[Any, float]] = (
        (getattr(note, "title", ""), 8.0),
        (getattr(note, "noesis_id", ""), 6.0),
        (getattr(note, "rel_path", ""), 5.0),
        (metadata.get("aliases", []), 6.0),
        (metadata.get("tags", []), 5.0),
        (metadata.get("scope", ""), 5.0),
        (metadata.get("purpose", ""), 4.0),
        (getattr(note, "body", ""), 1.0),
    )
    weighted: dict[str, float] = {}
    for value, weight in fields:
        if isinstance(value, (list, tuple, set)):
            text = " ".join(str(item) for item in value)
        else:
            text = str(value)
        for term in index_tokens(text):
            weighted[term] = weighted.get(term, 0.0) + weight
    return weighted


def note_sort_key(note: Any) -> tuple[str, str]:
    title = str(getattr(note, "title", "")).casefold()
    rel_path = str(getattr(note, "rel_path", ""))
    return title, rel_path
