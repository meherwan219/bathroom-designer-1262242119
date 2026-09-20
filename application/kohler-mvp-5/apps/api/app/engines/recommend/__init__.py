"""Recommendation engine — Phase 1 scope.

Full weighted soft-scoring (style/feature/sustainability/space/family,
see plan.md) is Phase 3. Phase 1 needs the generate endpoint to return
*something* real, so this does deterministic greedy selection: for
each required slot, pick the cheapest active, in-budget-band candidate
whose footprint fits the room. Never overrides a hard constraint —
the constraint engine re-checks the assembled set regardless.
"""
from __future__ import annotations

from app.engines.compat import attach_required_companions
from app.engines.compat_loader import load_compat_rules
from app.engines.domain import DesignSpec, PlacedItem, Product

_COMPAT_RULES = load_compat_rules()

ROLE_FOR_CATEGORY = {
    "toilet": "primary_toilet",
    "vanity": "primary_vanity",
    "faucet": "primary_faucet",
    "shower": "primary_shower",
    "bath": "primary_bath",
    "storage": "primary_storage",
}


def _fits_room(p: Product, spec: DesignSpec) -> bool:
    room = spec.room
    return (p.width_mm <= room.width_mm and p.depth_mm <= room.depth_mm) or \
           (p.depth_mm <= room.width_mm and p.width_mm <= room.depth_mm)


def select_candidates(spec: DesignSpec, catalog: list[Product]) -> list[PlacedItem]:
    """Greedy pick: cheapest fitting, active SKU per required category,
    in catalog order (which is itself sorted by price ascending by the
    caller for determinism). Required companion products (e.g. a
    wall-hung toilet's carrier system) are auto-attached afterward —
    see app.engines.compat."""
    chosen: list[PlacedItem] = []
    for category in spec.hard_required:
        candidates = [
            p for p in catalog
            if p.category == category and p.is_active and _fits_room(p, spec)
        ]
        if not candidates:
            continue  # validator will report the missing required slot
        cheapest = min(candidates, key=lambda p: p.price_inr)
        chosen.append(PlacedItem(role=ROLE_FOR_CATEGORY.get(category, category), product=cheapest))
    return attach_required_companions(chosen, catalog, _COMPAT_RULES)
