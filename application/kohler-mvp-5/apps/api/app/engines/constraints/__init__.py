"""Deterministic constraint engine.

Pure Python, no FastAPI/pydantic imports, so it unit-tests without
HTTP (see plan.md). Owns: room bounds, fixture footprint, clearances,
budget, compatibility, unique slots. Never optimizes aesthetics —
that is the recommendation engine's job, and it may never override a
hard failure produced here.

NKBA-inspired minimums (constraints_profile == "nkba_std"); a
"compact_apt" profile relaxes them for small-footprint urban units.
"""
from __future__ import annotations

from app.engines.compat import check_compat_graph
from app.engines.compat_loader import load_compat_rules
from app.engines.domain import DesignSpec, PlacedItem, Violation

_COMPAT_RULES = load_compat_rules()

PROFILES = {
    "nkba_std": {
        "toilet_front_mm": 600,
        "toilet_side_mm": 400,
        "vanity_approach_mm": 700,
        "shower_interior_min_mm": 900,
    },
    "compact_apt": {
        "toilet_front_mm": 500,
        "toilet_side_mm": 350,
        "vanity_approach_mm": 550,
        "shower_interior_min_mm": 800,
    },
}


def _profile(spec: DesignSpec) -> dict:
    return PROFILES.get(spec.constraints_profile, PROFILES["nkba_std"])


def check_room_containment(spec: DesignSpec, items: list[PlacedItem]) -> list[Violation]:
    """Every item's total footprint (own bbox + declared clearance) must
    fit inside the room's bounding box. This does not place items — it's
    a coarse feasibility check the layout engine's real placement must
    also satisfy."""
    violations: list[Violation] = []
    room = spec.room
    for item in items:
        p = item.product
        w, d = p.width_mm, p.depth_mm
        if w > room.width_mm and w > room.depth_mm:
            violations.append(Violation(
                code="footprint_exceeds_room",
                message=f"{p.name} ({w}x{d}mm) does not fit in a "
                        f"{room.width_mm}x{room.depth_mm}mm room in either orientation.",
            ))
    return violations


def check_clearances(spec: DesignSpec, items: list[PlacedItem]) -> list[Violation]:
    """Checks each item's required clearance envelope against the
    smaller room dimension as a coarse pre-placement feasibility gate.
    (The layout engine does the real geometric collision check once
    items are actually placed on the grid.)"""
    prof = _profile(spec)
    room = spec.room
    min_span = min(room.width_mm, room.depth_mm)
    violations: list[Violation] = []

    for item in items:
        p = item.product
        if p.category == "toilet":
            needed = p.depth_mm + prof["toilet_front_mm"]
            if needed > room.depth_mm and needed > room.width_mm:
                violations.append(Violation(
                    code="toilet_front_clearance",
                    message=f"{p.name} needs {needed}mm front clearance; "
                            f"room is only {room.width_mm}x{room.depth_mm}mm.",
                ))
        elif p.category == "vanity":
            approach = p.clearance_overrides.get("approach_mm", prof["vanity_approach_mm"])
            if approach > min_span:
                violations.append(Violation(
                    code="vanity_approach_clearance",
                    message=f"{p.name} needs {approach}mm approach clearance; "
                            f"room's shorter side is {min_span}mm.",
                ))
        elif p.category == "shower":
            interior = p.clearance_overrides.get("interior_min_mm", prof["shower_interior_min_mm"])
            if p.width_mm < interior or p.depth_mm < interior:
                violations.append(Violation(
                    code="shower_interior_too_small",
                    message=f"{p.name} interior ({p.width_mm}x{p.depth_mm}mm) is "
                            f"below the {interior}mm minimum for {spec.constraints_profile}.",
                ))
    return violations


def check_budget(spec: DesignSpec, items: list[PlacedItem]) -> list[Violation]:
    total = sum(item.product.price_inr for item in items)
    cap = spec.budget.max_inr
    if spec.budget.flexibility == "soft_10pct":
        cap = int(cap * 1.10)
    if total > cap:
        over_pct = round((total - spec.budget.max_inr) / spec.budget.max_inr * 100, 1)
        violations = [Violation(
            code="over_budget",
            message=f"Total \u20b9{total:,} exceeds budget \u20b9{spec.budget.max_inr:,} "
                     f"by {over_pct}%.",
        )]
        return violations
    return []


def check_unique_slots(items: list[PlacedItem]) -> list[Violation]:
    primary_roles = [i.role for i in items if i.role.startswith("primary_")]
    seen: dict[str, int] = {}
    for r in primary_roles:
        seen[r] = seen.get(r, 0) + 1
    return [
        Violation(code="duplicate_primary_slot", message=f"More than one {role}.")
        for role, count in seen.items() if count > 1
    ]


def check_compatibility(items: list[PlacedItem]) -> list[Violation]:
    """Faucet hole-count/spread must match the lavatory it pairs with.
    Phase 1 keeps this to the one pairing called out in plan.md; the
    full product_compat graph lands in Phase 3."""
    faucet = next((i.product for i in items if i.product.category == "faucet"), None)
    vanity = next((i.product for i in items if i.product.category == "vanity"), None)
    if not faucet or not vanity:
        return []

    faucet_holes = faucet.clearance_overrides.get("hole_count")
    vanity_holes = vanity.clearance_overrides.get("hole_count", faucet_holes)
    if faucet_holes is not None and vanity_holes is not None and faucet_holes != vanity_holes:
        return [Violation(
            code="faucet_lavatory_hole_mismatch",
            message=f"{faucet.name} needs {faucet_holes} holes; "
                    f"{vanity.name} is drilled for {vanity_holes}.",
        )]
    return []


def check_hard_constraints(spec: DesignSpec, items: list[PlacedItem]) -> list[Violation]:
    """Runs every hard check and concatenates violations. Order matches
    the solver slot order in plan.md so the first-listed failure is
    usually the most actionable one to show a user."""
    violations: list[Violation] = []
    violations += check_room_containment(spec, items)
    violations += check_clearances(spec, items)
    violations += check_unique_slots(items)
    violations += check_compatibility(items)
    violations += check_compat_graph(items, _COMPAT_RULES)
    violations += check_budget(spec, items)
    return violations
