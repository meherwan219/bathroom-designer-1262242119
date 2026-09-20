"""Guards the exact narrative demo.py prints and README's demo
walkthrough quotes numbers from, so a future engine change can't
silently break the scripted demo without a test failing.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import services, store
from app.ai.modify import run_chat_turn
from app.engines.catalog_loader import load_catalog

CATALOG = load_catalog()


class DemoScriptTests(unittest.TestCase):

    def test_small_apartment_eco_scenario_end_to_end(self):
        created = services.create_design({
            "room": {"width_mm": 1800, "depth_mm": 2100, "wet_walls": ["N"]},
            "budget": {"max_inr": 80_000},
            "hard_required": ["toilet", "vanity", "faucet"],
            "preferences": {"styles": ["eco"]},
            "constraints_profile": "compact_apt",
        })

        gen = services.generate(created["id"])
        self.assertEqual(gen["hard_violations"], [])
        self.assertLessEqual(gen["totals"]["price_inr"], gen["totals"]["budget_inr"])

        spec_dict = store.spec_to_dict(store.get(created["id"])["spec"])
        add_shower = lambda s, u: (
            '{"hard_required": ["toilet","vanity","faucet","shower"], '
            '"preferences": {"features": ["rain shower"]}}'
        )
        turn1 = run_chat_turn(spec_dict, "add a rain shower", CATALOG, add_shower)
        self.assertFalse(turn1["generate_result"]["feasible"])
        self.assertGreaterEqual(len(turn1["alternatives"]), 1)
        feasible_alt = next((a for a in turn1["alternatives"] if a["would_be_feasible"]), None)
        self.assertIsNotNone(feasible_alt, "at least one repair alternative must actually work")

        drop_shower = lambda s, u, _d=feasible_alt["delta"]: json.dumps(_d)
        turn2 = run_chat_turn(turn1["spec"], "drop the shower", CATALOG, drop_shower)
        self.assertTrue(turn2["generate_result"]["feasible"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
