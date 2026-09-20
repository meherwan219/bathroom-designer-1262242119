"""Weighted soft scoring, per plan.md's recommendation algorithm:

    score(itemset) = w_style*style_match + w_feat*feature_coverage
                    + w_sust*normalized_sustainability
                    + w_space*circulation_ratio
                    + w_family*collection_coherence
                    - w_waste*unused_budget_penalty

Default weights per plan.md: style 0.3, features 0.25, sustainability
0.2, space 0.15, family 0.1. Never consulted by the constraint engine
and never overrides a hard failure \u2014 this only ranks among itemsets
that already passed app.engines.constraints.
"""
from __future__ import annotations

from collections import Counter

from app.engines.domain import DesignSpec, PlacedItem, Product

WEIGHTS = {
    "style": 0.30,
    "feature": 0.25,
    "sustainability": 0.20,
    "space": 0.15,
    "family": 0.10,
    "waste": 0.05,  # subtracted, small tie-breaker per plan.md
}

# Target occupied-floor-area fraction beyond which extra space stops
# helping the space-efficiency score (avoids rewarding a nearly-empty
# room as "efficient" just because nothing collides).
SPACE_TARGET_FRACTION = 0.5


def style_match(items: list[PlacedItem], preferred_styles: tuple[str, ...]) -> float:
    if not preferred_styles:
        return 0.5  # neutral \u2014 no stated preference to reward or penalize
    preferred = set(preferred_styles)
    if not items:
        return 0.0
    hits = sum(1 for i in items if preferred & set(i.product.style_tags))
    return hits / len(items)


def feature_coverage(items: list[PlacedItem], preferred_features: tuple[str, ...]) -> float:
    if not preferred_features:
        return 0.5
    all_tags = set()
    for i in items:
        all_tags |= set(i.product.style_tags)
    matched = set(preferred_features) & all_tags
    return len(matched) / len(preferred_features)


def sustainability_score(items: list[PlacedItem]) -> float:
    if not items:
        return 0.0
    return sum(i.product.sustainability_score for i in items) / len(items) / 100.0


def space_efficiency(spec: DesignSpec, items: list[PlacedItem]) -> float:
    room_area = spec.room.width_mm * spec.room.depth_mm
    if room_area <= 0:
        return 0.0
    occupied = sum(i.product.width_mm * i.product.depth_mm for i in items)
    fraction = occupied / room_area
    return min(fraction / SPACE_TARGET_FRACTION, 1.0)


def family_coherence(items: list[PlacedItem]) -> float:
    if not items:
        return 0.0
    families = [i.product.family for i in items if i.product.family]
    if not families:
        return 0.0
    most_common_count = Counter(families).most_common(1)[0][1]
    return most_common_count / len(items)


def waste_penalty(spec: DesignSpec, items: list[PlacedItem]) -> float:
    total = sum(i.product.price_inr for i in items)
    budget = spec.budget.max_inr
    if budget <= 0 or total > budget:
        return 0.0  # over-budget is a hard violation elsewhere, not a soft waste signal
    return (budget - total) / budget


def score_itemset(spec: DesignSpec, items: list[PlacedItem]) -> dict:
    """Returns the full score breakdown (each component + the weighted
    total), so the API can expose 'why' this itemset ranked where it
    did \u2014 not just a single opaque number."""
    style = style_match(items, spec.preferences.styles)
    feature = feature_coverage(items, spec.preferences.features)
    sustainability = sustainability_score(items)
    space = space_efficiency(spec, items)
    family = family_coherence(items)
    waste = waste_penalty(spec, items)

    total = (
        WEIGHTS["style"] * style
        + WEIGHTS["feature"] * feature
        + WEIGHTS["sustainability"] * sustainability
        + WEIGHTS["space"] * space
        + WEIGHTS["family"] * family
        - WEIGHTS["waste"] * waste
    )

    return {
        "style_match": round(style, 3),
        "feature_coverage": round(feature, 3),
        "sustainability": round(sustainability, 3),
        "space_efficiency": round(space, 3),
        "family_coherence": round(family, 3),
        "waste_penalty": round(waste, 3),
        "total": round(total, 4),
    }
