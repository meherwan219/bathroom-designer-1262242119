"""Catalog endpoints: browse products and hybrid search.

Wired to the real seed catalog (Phase 1) and the RAG hybrid search
(Phase 2, app.ai.rag — see that module's docstring for the honest
caveat: local keyword/token-overlap search, not pgvector embeddings).
"""
from fastapi import APIRouter, HTTPException, Query

from app.ai.rag import search_catalog
from app.engines.catalog_loader import load_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])

_CATALOG = load_catalog()


def _to_dict(p) -> dict:
    return {
        "id": p.id, "sku": p.sku, "name": p.name, "category": p.category,
        "family": p.family, "collection": p.collection,
        "width_mm": p.width_mm, "depth_mm": p.depth_mm, "height_mm": p.height_mm,
        "price_inr": p.price_inr, "install_type": p.install_type,
        "style_tags": list(p.style_tags), "sustainability_score": p.sustainability_score,
    }


@router.get("/products")
def list_products(
    category: str | None = Query(default=None),
    max_price: int | None = Query(default=None),
    style: str | None = Query(default=None),
):
    """Filter catalog by category, price, style tag."""
    items = _CATALOG
    if category:
        items = [p for p in items if p.category == category]
    if max_price is not None:
        items = [p for p in items if p.price_inr <= max_price]
    if style:
        items = [p for p in items if style in p.style_tags]
    return {"items": [_to_dict(p) for p in items], "count": len(items)}


@router.get("/products/{sku}")
def get_product(sku: str):
    """Full spec for a single SKU. Compatibility graph (Phase 3) not
    yet attached — see app.engines.constraints.check_compatibility for
    the one pairing rule that exists today."""
    match = next((p for p in _CATALOG if p.sku == sku), None)
    if match is None:
        raise HTTPException(status_code=404, detail="sku not found")
    return _to_dict(match)


@router.post("/search")
def search_products(payload: dict):
    """Hybrid keyword + similarity search. payload: {"query": str,
    "top_k"?: int, "category"?: str}."""
    query = payload.get("query", "")
    top_k = payload.get("top_k", 5)
    category = payload.get("category")
    pool = [p for p in _CATALOG if p.category == category] if category else _CATALOG
    results = search_catalog(query, pool, top_k=top_k)
    return {"results": [_to_dict(p) for p in results]}
