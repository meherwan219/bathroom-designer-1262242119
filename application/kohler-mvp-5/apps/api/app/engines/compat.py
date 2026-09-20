"""Product compatibility graph checks (plan.md's `product_compat`
table: requires | incompatible | finish_match | rough_in_match).

`requires` and `incompatible` are hard constraints — enforced here and
consumed by app.engines.constraints. `finish_match` is a soft signal
folded into the recommend engine's family/collection coherence score,
not enforced here.

Two responsibilities kept separate on purpose:
  - attach_required_companions: proactively satisfies `requires` edges
    (e.g. a wall-hung toilet pulls in its carrier system) so a normal
    selection doesn't spuriously fail just because a companion product
    wasn't independently requested.
  - check_compat_graph: the actual hard-constraint check, which still
    runs on the final item list as a safety net — if a `requires`
    companion couldn't be attached (e.g. inactive/missing SKU), or a
    chat edit manually assembled an `incompatible` pair, this is what
    catches it.
"""
from __future__ import annotations

from app.engines.compat_loader import CompatRule
from app.engines.domain import PlacedItem, Product, Violation


def attach_required_companions(
    items: list[PlacedItem],
    catalog: list[Product],
    rules: list[CompatRule],
) -> list[PlacedItem]:
    by_id = {p.id: p for p in catalog}
    present_ids = {i.product.id for i in items}
    result = list(items)

    for rule in rules:
        if rule.relation != "requires":
            continue
        if rule.product_id not in present_ids:
            continue
        if rule.other_id in present_ids:
            continue
        companion = by_id.get(rule.other_id)
        if companion is None or not companion.is_active:
            continue  # check_compat_graph will report this as unresolved
        result.append(PlacedItem(role=f"required_{companion.category}", product=companion))
        present_ids.add(companion.id)

    return result


def check_compat_graph(items: list[PlacedItem], rules: list[CompatRule]) -> list[Violation]:
    present_ids = {i.product.id for i in items}
    by_id = {i.product.id: i.product for i in items}
    violations: list[Violation] = []

    for rule in rules:
        if rule.product_id not in present_ids:
            continue

        if rule.relation == "incompatible" and rule.other_id in present_ids:
            a, b = by_id[rule.product_id], by_id[rule.other_id]
            violations.append(Violation(
                code="incompatible_products",
                message=f"{a.name} is incompatible with {b.name}. {rule.notes}".strip(),
            ))
        elif rule.relation == "requires" and rule.other_id not in present_ids:
            a = by_id[rule.product_id]
            violations.append(Violation(
                code="missing_required_companion",
                message=f"{a.name} requires a compatible companion product that isn't selected. {rule.notes}".strip(),
            ))

    return violations
