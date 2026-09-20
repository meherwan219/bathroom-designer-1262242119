"""Top-3 itemset generation, per plan.md's recommendation algorithm:

    1. Candidate pool per slot (top-N per category, not just cheapest)
    2. Compatibility graph attach/prune
    3. Placement + hard-constraint filtering
    4. Rank remaining by weighted soft score
    5. return top_3 itemsets + traces

Bounded combinatorics: at most POOL_SIZE candidates per required
category, so worst case is POOL_SIZE^len(hard_required) combinations
\u2014 trivial at this catalog's scale (a few hundred at most) and fast
in pure Python with no DB round-trips.
"""
from __future__ import annotations

import itertools

from app.engines.compat import attach_required_companions
from app.engines.compat_loader import load_compat_rules
from app.engines.constraints import check_hard_constraints
from app.engines.domain import DesignSpec, PlacedItem, Product
from app.engines.layout import place_items, to_layout_ir
from app.engines.recommend import ROLE_FOR_CATEGORY, _fits_room
from app.engines.recommend.scoring import score_itemset

POOL_SIZE = 3
TOP_K = 3

_COMPAT_RULES = load_compat_rules()


def _category_pool(category: str, catalog: list[Product], spec: DesignSpec) -> list[Product]:
    """Top-POOL_SIZE cheapest fitting candidates, UNION top-POOL_SIZE
    fitting candidates that match a stated style/feature preference.
    Pure price-based pooling would never surface a specialty item
    (e.g. a rain shower system) that isn't among the cheapest options
    in its category, even when the person explicitly asked for it \u2014
    this union is what lets a preference actually pull a non-cheapest
    item into consideration, while feasibility/hard constraints still
    decide whether it survives."""
    fitting = [p for p in catalog if p.category == category and p.is_active and _fits_room(p, spec)]
    preferred = set(spec.preferences.styles) | set(spec.preferences.features)

    cheapest = sorted(fitting, key=lambda p: p.price_inr)[:POOL_SIZE]
    preferred_matches = sorted(
        (p for p in fitting if preferred & set(p.style_tags)),
        key=lambda p: p.price_inr,
    )[:POOL_SIZE]

    pool: list[Product] = []
    seen_ids: set[str] = set()
    for p in cheapest + preferred_matches:
        if p.id not in seen_ids:
            pool.append(p)
            seen_ids.add(p.id)
    return pool


def _water_baseline(category: str, catalog: list[Product]) -> float:
    with_water = [p.water_use for p in catalog if p.category == category and p.water_use is not None]
    return sum(with_water) / len(with_water) if with_water else 0.0


def _build_trace(spec: DesignSpec, items: list[PlacedItem], catalog: list[Product], score: dict) -> dict:
    preferred = set(spec.preferences.styles) | set(spec.preferences.features)
    matched_tags = sorted(preferred & {t for i in items for t in i.product.style_tags})

    total_water = sum(i.product.water_use for i in items if i.product.water_use is not None)
    baseline_water = sum(_water_baseline(i.product.category, catalog) for i in items if i.product.water_use is not None)
    water_savings_pct = (
        round((baseline_water - total_water) / baseline_water * 100, 1)
        if baseline_water > 0 else 0.0
    )

    return {
        "matched_tags": matched_tags,
        "total_water_use_lpf_or_gpm": round(total_water, 2),
        "baseline_water_use": round(baseline_water, 2),
        "water_savings_pct_vs_baseline": water_savings_pct,
        "score_breakdown": score,
    }


def generate_top_itemsets(spec: DesignSpec, catalog: list[Product], k: int = TOP_K) -> list[dict]:
    """Returns up to k itemsets, each:
        {items, feasible, hard_violations, layout_ir, totals, score, trace}
    Feasible itemsets are always ranked ahead of infeasible ones; within
    each group, ranked by descending soft score total. Always returns
    at least one itemset (even if none are feasible) so the caller has
    something concrete to explain, per plan.md's explainer contract.
    """
    pools = {cat: _category_pool(cat, catalog, spec) for cat in spec.hard_required}
    categories = [c for c in spec.hard_required if pools[c]]

    if not categories:
        return []

    seen_signatures: set[tuple] = set()
    candidates: list[dict] = []

    for combo in itertools.product(*(pools[c] for c in categories)):
        base_items = [
            PlacedItem(role=ROLE_FOR_CATEGORY.get(cat, cat), product=p)
            for cat, p in zip(categories, combo)
        ]
        items = attach_required_companions(base_items, catalog, _COMPAT_RULES)

        signature = tuple(sorted(i.product.id for i in items))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        violations = check_hard_constraints(spec, items)
        placed, placement_violations = place_items(spec, items)
        all_violations = violations + placement_violations
        feasible = len(all_violations) == 0

        score = score_itemset(spec, items)
        layout_ir = to_layout_ir(spec, placed) if placed else {}
        total_price = sum(i.product.price_inr for i in items)

        candidates.append({
            "items": items,
            "feasible": feasible,
            "hard_violations": all_violations,
            "layout_ir": layout_ir,
            "totals": {"price_inr": total_price, "budget_inr": spec.budget.max_inr},
            "score": score,
            "trace": _build_trace(spec, items, catalog, score),
        })

    candidates.sort(key=lambda c: (not c["feasible"], -c["score"]["total"]))
    return candidates[:k]


def serialize_itemset(it: dict) -> dict:
    """Converts an itemset's dataclass objects (PlacedItem, Violation)
    into plain JSON-safe dicts, matching the shape app.services has
    always returned for `items` / `hard_violations`."""
    return {
        "feasible": it["feasible"],
        "items": [
            {"role": i.role, "sku": i.product.sku, "name": i.product.name,
             "category": i.product.category, "price_inr": i.product.price_inr}
            for i in it["items"]
        ],
        "hard_violations": [{"code": v.code, "message": v.message} for v in it["hard_violations"]],
        "layout_ir": it["layout_ir"],
        "totals": it["totals"],
        "score": it["score"],
        "trace": it["trace"],
    }
