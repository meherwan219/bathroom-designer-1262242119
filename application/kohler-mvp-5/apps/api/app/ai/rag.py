"""Catalog RAG: hybrid keyword + similarity search.

plan.md specifies pgvector embeddings over product_embeddings for the
real system. This sandbox has no DB and no network to call an
embeddings API, so this module implements the same *contract* — score
and rank catalog products against a free-text query, return top-k —
with a local, dependency-free approximation: keyword substring
matching (name/family/collection/style_tags) blended with token-set
(Jaccard) similarity as a stand-in for cosine similarity over real
embeddings. It's honest about being weaker than real embeddings (no
semantic generalization beyond shared words), but it satisfies the
guardrail that actually matters: retrieved results are always a
subset of the catalog, never hallucinated.

Swap point: replace `_score` with a pgvector cosine-similarity query
and nothing above this module needs to change — callers only depend
on `search_catalog(query, catalog, top_k) -> list[Product]`.
"""
from __future__ import annotations

import re

from app.engines.domain import Product

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _product_text(p: Product) -> str:
    return " ".join([p.name, p.family, p.collection, p.category, " ".join(p.style_tags), p.finish])


def _score(query_tokens: set[str], p: Product) -> float:
    doc_tokens = _tokenize(_product_text(p))
    if not query_tokens or not doc_tokens:
        return 0.0

    overlap = query_tokens & doc_tokens
    jaccard = len(overlap) / len(query_tokens | doc_tokens)

    # Keyword bonus: an exact substring hit (e.g. "wall-hung" -> "wall")
    # in the product name counts for more than incidental tag overlap.
    name_tokens = _tokenize(p.name)
    keyword_bonus = 0.5 * len(query_tokens & name_tokens) / max(len(query_tokens), 1)

    return jaccard + keyword_bonus


def search_catalog(query: str, catalog: list[Product], top_k: int = 5) -> list[Product]:
    """Returns up to top_k products ranked by relevance to `query`.
    Always a subset of `catalog` — this function only reorders and
    filters, it never constructs a Product that wasn't passed in."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = [(p, _score(query_tokens, p)) for p in catalog]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [p for p, _ in scored[:top_k]]


def filter_by_hard_constraints(products: list[Product], category: str | None = None) -> list[Product]:
    """Applies the same category/active gates the recommend engine
    uses, so RAG results handed to the LLM are already pre-filtered —
    per plan.md: 'engines filter by hard constraints before ranking.'
    Full clearance/budget checks still run in app.engines.constraints
    once a candidate is actually selected into a slot.
    """
    result = [p for p in products if p.is_active]
    if category:
        result = [p for p in result if p.category == category]
    return result
