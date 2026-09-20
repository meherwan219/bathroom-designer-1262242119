"""Phase 3 soft-scoring and top-3 itemset tests, per plan.md's
recommendation algorithm section.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.catalog_loader import load_catalog
from app.engines.domain import Budget, DesignSpec, PlacedItem, Preferences, Room
from app.engines.recommend.itemsets import generate_top_itemsets
from app.engines.recommend.scoring import score_itemset

CATALOG = load_catalog()


def product(sku: str):
    return next(p for p in CATALOG if p.sku == sku)


class ScoringTests(unittest.TestCase):

    def test_style_preference_changes_ranking(self):
        """The same two itemsets must rank differently depending on
        stated style preference \u2014 scoring must actually respond to
        the spec, not just to fixed item properties."""
        modern_items = [PlacedItem(role="primary_toilet", product=product("K-6299-IN-0"))]
        classic_items = [PlacedItem(role="primary_toilet", product=product("K-3493-IN-0"))]

        room = Room(width_mm=2400, depth_mm=2700)
        modern_spec = DesignSpec(room=room, budget=Budget(max_inr=200_000),
                                  preferences=Preferences(styles=("modern",)))
        classic_spec = DesignSpec(room=room, budget=Budget(max_inr=200_000),
                                   preferences=Preferences(styles=("classic",)))

        # Under a "modern" preference, the modern item must outscore the classic one.
        self.assertGreater(
            score_itemset(modern_spec, modern_items)["total"],
            score_itemset(modern_spec, classic_items)["total"],
        )
        # Flip the preference: ranking should flip too.
        self.assertGreater(
            score_itemset(classic_spec, classic_items)["total"],
            score_itemset(classic_spec, modern_items)["total"],
        )

    def test_no_preference_is_neutral_not_penalizing(self):
        items = [PlacedItem(role="primary_toilet", product=product("K-3493-IN-0"))]
        spec = DesignSpec(room=Room(width_mm=2400, depth_mm=2700), budget=Budget(max_inr=200_000))
        score = score_itemset(spec, items)
        self.assertEqual(score["style_match"], 0.5)
        self.assertEqual(score["feature_coverage"], 0.5)

    def test_weights_match_plan_defaults(self):
        from app.engines.recommend.scoring import WEIGHTS
        self.assertAlmostEqual(WEIGHTS["style"], 0.30)
        self.assertAlmostEqual(WEIGHTS["feature"], 0.25)
        self.assertAlmostEqual(WEIGHTS["sustainability"], 0.20)
        self.assertAlmostEqual(WEIGHTS["space"], 0.15)
        self.assertAlmostEqual(WEIGHTS["family"], 0.10)


class TopItemsetTests(unittest.TestCase):

    def test_returns_up_to_three_distinct_itemsets(self):
        spec = DesignSpec(
            room=Room(width_mm=2400, depth_mm=2700, wet_walls=("N",)),
            budget=Budget(max_inr=250_000),
            hard_required=("toilet", "vanity", "shower"),
        )
        results = generate_top_itemsets(spec, CATALOG, k=3)
        self.assertLessEqual(len(results), 3)
        signatures = [tuple(sorted(i.product.id for i in r["items"])) for r in results]
        self.assertEqual(len(signatures), len(set(signatures)), "itemsets must be distinct")

    def test_feasible_itemsets_ranked_before_infeasible(self):
        spec = DesignSpec(
            room=Room(width_mm=2400, depth_mm=2700, wet_walls=("N",)),
            budget=Budget(max_inr=250_000),
            hard_required=("toilet", "vanity", "shower"),
        )
        results = generate_top_itemsets(spec, CATALOG, k=3)
        feasible_flags = [r["feasible"] for r in results]
        # once a False appears, no True should follow
        self.assertEqual(feasible_flags, sorted(feasible_flags, key=lambda f: not f))

    def test_results_sorted_by_score_within_feasibility_group(self):
        spec = DesignSpec(
            room=Room(width_mm=2400, depth_mm=2700, wet_walls=("N",)),
            budget=Budget(max_inr=250_000),
            hard_required=("toilet", "vanity", "shower"),
        )
        results = generate_top_itemsets(spec, CATALOG, k=3)
        feasible = [r for r in results if r["feasible"]]
        scores = [r["score"]["total"] for r in feasible]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_trace_reports_water_savings_and_matched_tags(self):
        spec = DesignSpec(
            room=Room(width_mm=2400, depth_mm=2700, wet_walls=("N",)),
            budget=Budget(max_inr=250_000),
            hard_required=("toilet", "shower"),
            preferences=Preferences(styles=("modern",)),
        )
        results = generate_top_itemsets(spec, CATALOG, k=1)
        self.assertEqual(len(results), 1)
        trace = results[0]["trace"]
        self.assertIn("water_savings_pct_vs_baseline", trace)
        self.assertIn("matched_tags", trace)

    def test_empty_hard_required_returns_no_itemsets(self):
        spec = DesignSpec(room=Room(width_mm=2400, depth_mm=2700), budget=Budget(max_inr=200_000))
        self.assertEqual(generate_top_itemsets(spec, CATALOG, k=3), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
