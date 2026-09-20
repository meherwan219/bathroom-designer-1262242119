"""Loads the seed catalog into Product dataclasses.

Stdlib-only (json + pathlib) so engines can be tested without a DB
connection. app/seed/products.json is the single source of truth for
Phase 1; swapping this for a real `products` table query (per the DB
schema in plan.md) is a drop-in replacement — callers only depend on
this function returning list[Product].
"""
from __future__ import annotations

import json
from pathlib import Path

from app.engines.domain import Product

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "products.json"


def load_catalog(path: Path = DEFAULT_SEED_PATH) -> list[Product]:
    raw = json.loads(path.read_text())
    products = [Product.from_json(d) for d in raw if d.get("is_active", True)]
    return sorted(products, key=lambda p: p.price_inr)
