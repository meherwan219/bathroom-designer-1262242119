"""Compatibility graph tests, per plan.md's hard-constraint bullet:
'Compatibility: faucet\u2194lavatory hole count; toilet rough-in; shower
valve\u2194trim' and the `product_compat` table (requires/incompatible/
finish_match/rough_in_match).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.catalog_loader import load_catalog
from app.engines.compat import attach_required_companions, check_compat_graph
from app.engines.compat_loader import load_compat_rules
from app.engines.domain import PlacedItem

CATALOG = load_catalog()
RULES = load_compat_rules()


def product(sku: str):
    return next(p for p in CATALOG if p.sku == sku)


class CompatGraphTests(unittest.TestCase):

    def test_requires_companion_gets_auto_attached(self):
        """Selecting a wall-hung toilet alone should auto-pull its
        in-wall carrier system \u2014 a real BOM would need both."""
        toilet = product("K-6299-IN-0")  # Veil wall-hung, requires K-WC-100
        items = [PlacedItem(role="primary_toilet", product=toilet)]
        attached = attach_required_companions(items, CATALOG, RULES)
        skus = {i.product.sku for i in attached}
        self.assertIn("K-WC-100", skus)

    def test_missing_required_companion_is_a_violation(self):
        """If a requires-companion truly can't be resolved (simulated
        here by NOT auto-attaching), the graph check must catch it \u2014
        this is the safety net, not just the auto-attach convenience."""
        toilet = product("K-6299-IN-0")
        items = [PlacedItem(role="primary_toilet", product=toilet)]  # no carrier
        violations = check_compat_graph(items, RULES)
        codes = {v.code for v in violations}
        self.assertIn("missing_required_companion", codes)

    def test_incompatible_flange_kit_is_rejected(self):
        """A 300mm rough-in toilet with a 400mm flange kit must fail \u2014
        this is the 'toilet rough-in' hard check from plan.md."""
        toilet = product("K-3814-IN-0")     # Cimarron, 300mm rough-in
        wrong_kit = product("K-FLANGE-400")  # for 400mm rough-in
        items = [
            PlacedItem(role="primary_toilet", product=toilet),
            PlacedItem(role="required_accessory", product=wrong_kit),
        ]
        violations = check_compat_graph(items, RULES)
        codes = {v.code for v in violations}
        self.assertIn("incompatible_products", codes)

    def test_correct_flange_kit_passes(self):
        toilet = product("K-3814-IN-0")
        right_kit = product("K-FLANGE-300")
        items = [
            PlacedItem(role="primary_toilet", product=toilet),
            PlacedItem(role="required_accessory", product=right_kit),
        ]
        violations = check_compat_graph(items, RULES)
        self.assertEqual(violations, [])

    def test_rain_shower_head_requires_a_base(self):
        """Shower valve/trim-style requires edge: a head-only system
        needs a base; selecting it alone must be caught."""
        head_only = product("K-9107-IN")  # Awaken rain shower head system
        items = [PlacedItem(role="primary_shower", product=head_only)]
        violations = check_compat_graph(items, RULES)
        codes = {v.code for v in violations}
        self.assertIn("missing_required_companion", codes)

        attached = attach_required_companions(items, CATALOG, RULES)
        violations_after = check_compat_graph(attached, RULES)
        self.assertEqual(violations_after, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
