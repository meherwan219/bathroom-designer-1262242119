"""Validator: the final accept/reject pass.

Property under test: no accepted design has hard_violations. This
module owns that property — it is the only place "feasible" gets
decided. It never trusts LLM-proposed geometry; it only trusts the
layout engine's own placement output.
"""
from __future__ import annotations

from app.engines.constraints import check_hard_constraints
from app.engines.domain import DesignSpec, PlacedItem, Violation
from app.engines.layout import place_items, to_layout_ir


def generate_design(spec: DesignSpec, selected_items: list[PlacedItem]) -> dict:
    """Runs constraints -> layout -> re-validate, and returns the same
    response shape the /designs/{id}/generate endpoint serializes.
    """
    pre_violations: list[Violation] = check_hard_constraints(spec, selected_items)

    placed, placement_violations = place_items(spec, selected_items)
    all_violations = pre_violations + placement_violations

    missing = [
        cat for cat in spec.hard_required
        if not any(i.product.category == cat for i in selected_items)
    ]
    for cat in missing:
        all_violations.append(Violation(
            code="no_feasible_candidate",
            message=f"No in-budget, room-fitting '{cat}' SKU was found in the catalog.",
        ))

    layout_ir = to_layout_ir(spec, placed) if placed else {}
    total_price = sum(i.product.price_inr for i in selected_items)

    return {
        "feasible": len(all_violations) == 0,
        "layout_ir": layout_ir,
        "items": [
            {
                "role": i.role,
                "sku": i.product.sku,
                "name": i.product.name,
                "category": i.product.category,
                "price_inr": i.product.price_inr,
            }
            for i in selected_items
        ],
        "totals": {"price_inr": total_price, "budget_inr": spec.budget.max_inr},
        "hard_violations": [{"code": v.code, "message": v.message} for v in all_violations],
    }
