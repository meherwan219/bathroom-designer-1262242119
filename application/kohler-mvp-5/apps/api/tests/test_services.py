"""Service-layer tests: the full create -> generate -> validate ->
patch -> re-generate flow, exercised the same way the API router will
call it, but without needing FastAPI installed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import services

GOOD_PAYLOAD = {
    "room": {"width_mm": 2400, "depth_mm": 2700, "wet_walls": ["N"]},
    "budget": {"max_inr": 300_000},
    "hard_required": ["toilet", "shower", "vanity"],
}


class ServiceFlowTests(unittest.TestCase):

    def test_create_generate_validate_round_trip(self):
        created = services.create_design(GOOD_PAYLOAD)
        self.assertEqual(created["status"], "draft")

        gen = services.generate(created["id"])
        self.assertEqual(gen["hard_violations"], [])
        primary_items = [i for i in gen["items"] if i["role"].startswith("primary_")]
        self.assertEqual(len(primary_items), 3)
        self.assertGreater(len(gen["layout_ir"]["objects"]), 0)

        val = services.validate(created["id"])
        self.assertEqual(val["hard_violations"], [])

        got = services.get_design(created["id"])
        self.assertEqual(got["status"], "feasible")

    def test_patch_then_regenerate_can_flip_infeasible(self):
        created = services.create_design(GOOD_PAYLOAD)
        services.generate(created["id"])

        services.update_spec(created["id"], {"budget": {"max_inr": 1_000}})
        gen2 = services.generate(created["id"])
        codes = {v["code"] for v in gen2["hard_violations"]}
        self.assertIn("over_budget", codes)

        got = services.get_design(created["id"])
        self.assertEqual(got["status"], "failed")

    def test_unknown_design_raises_not_found(self):
        with self.assertRaises(services.DesignNotFound):
            services.get_design("does-not-exist")
        with self.assertRaises(services.DesignNotFound):
            services.generate("does-not-exist")

    def test_validate_before_generate_raises_conflict(self):
        created = services.create_design(GOOD_PAYLOAD)
        with self.assertRaises(services.DesignConflict):
            services.validate(created["id"])

    def test_select_alternative_persists_and_is_stable(self):
        created = services.create_design(GOOD_PAYLOAD)
        gen = services.generate(created["id"])
        self.assertGreaterEqual(len(gen["recommendation_alternatives"]), 1)

        target_rank = gen["recommendation_alternatives"][0]["rank"]
        switched = services.select_alternative(created["id"], target_rank)
        self.assertEqual(switched["soft_scores"], gen["recommendation_alternatives"][0]["score"])

        got = services.get_design(created["id"])
        self.assertEqual(got["last_result"]["rank"], target_rank)

    def test_select_alternative_out_of_range_raises(self):
        created = services.create_design(GOOD_PAYLOAD)
        services.generate(created["id"])
        with self.assertRaises(services.AlternativeNotFound):
            services.select_alternative(created["id"], 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
