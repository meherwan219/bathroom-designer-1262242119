"""Golden-room tests, per plan.md's testing-strategy table:

  Constraint unit tests | Golden rooms: 1500x2000 fail double vanity;
  2400x2700 pass toilet+shower+lav; budget cliff
  Compatibility | Faucet 8" spread vs single-hole lav must fail
  Layout | Overlap, door swing, out-of-room, wet-wall drain

Written against unittest (stdlib) rather than pytest, since this
sandbox has no network to install pytest. `python3 -m unittest
discover` runs these with zero dependencies. Swapping the runner to
pytest later is a no-op — no fixtures or pytest-only syntax used.

Property under test throughout: no accepted design has
hard_violations.length > 0 (see app/engines/validate).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.catalog_loader import load_catalog
from app.engines.constraints import check_compatibility, check_hard_constraints
from app.engines.domain import Budget, DesignSpec, PlacedItem, Product, Room
from app.engines.layout import place_items
from app.engines.recommend import select_candidates
from app.engines.validate import generate_design

CATALOG = load_catalog()


def product(sku: str) -> Product:
    return next(p for p in CATALOG if p.sku == sku)


class GoldenRoomTests(unittest.TestCase):

    def test_1500x2000_fails_double_vanity(self):
        """A double-vanity request is a duplicate primary slot and must
        be rejected regardless of whether either vanity individually fits."""
        room = Room(width_mm=1500, depth_mm=2000)
        spec = DesignSpec(room=room, budget=Budget(max_inr=200_000))
        vanity = product("K-99640T-IN-SM")  # 600mm vanity, fits fine alone
        items = [
            PlacedItem(role="primary_vanity", product=vanity),
            PlacedItem(role="primary_vanity", product=vanity),
        ]
        violations = check_hard_constraints(spec, items)
        codes = {v.code for v in violations}
        self.assertIn("duplicate_primary_slot", codes)

    def test_2400x2700_passes_toilet_shower_lav(self):
        """The plan's canonical 'passes' golden room: a mid-size bathroom
        with the three core fixtures and generous budget should come
        back fully feasible with zero hard violations."""
        room = Room(width_mm=2400, depth_mm=2700, wet_walls=("N",))
        spec = DesignSpec(
            room=room,
            budget=Budget(max_inr=300_000),
            hard_required=("toilet", "shower", "vanity"),
        )
        selected = select_candidates(spec, CATALOG)
        result = generate_design(spec, selected)
        self.assertEqual(result["hard_violations"], [], result["hard_violations"])
        self.assertTrue(result["feasible"])
        primary_items = [i for i in result["items"] if i["role"].startswith("primary_")]
        self.assertEqual(len(primary_items), 3)

    def test_budget_cliff(self):
        """Same room/requirements as the passing case, but the budget is
        set just below the cheapest feasible total: must fail on price,
        not on geometry."""
        room = Room(width_mm=2400, depth_mm=2700, wet_walls=("N",))
        spec = DesignSpec(
            room=room,
            budget=Budget(max_inr=5_000),  # deliberately far under any real total
            hard_required=("toilet", "shower", "vanity"),
        )
        selected = select_candidates(spec, CATALOG)
        result = generate_design(spec, selected)
        codes = {v["code"] for v in result["hard_violations"]}
        self.assertIn("over_budget", codes)
        self.assertFalse(result["feasible"])

    def test_faucet_hole_mismatch_fails(self):
        """Faucet 8in widespread (3-hole) vs a single-hole lavatory must
        be rejected by the compatibility check."""
        faucet = product("K-R37026-4D")  # 3-hole, 200mm spread
        vanity = Product.from_json({
            "id": "v-test", "sku": "TEST-1H", "name": "Test Single-Hole Lav",
            "category": "vanity", "family": "Test", "collection": "Test",
            "width_mm": 500, "depth_mm": 400, "height_mm": 850, "price_inr": 10000,
            "install_type": "floor", "water_use": None, "finish": "white",
            "style_tags": [], "sustainability_score": 50,
            "requires_supply": False, "requires_drain": False,
            "clearance_overrides": {"hole_count": 1}, "is_active": True,
        })
        items = [
            PlacedItem(role="primary_faucet", product=faucet),
            PlacedItem(role="primary_vanity", product=vanity),
        ]
        violations = check_compatibility(items)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].code, "faucet_lavatory_hole_mismatch")

    def test_layout_rejects_overlap(self):
        """Two fixtures whose combined width exceeds the wall they share
        must be reported as a collision, not silently overlapped."""
        room = Room(width_mm=900, depth_mm=1200, wet_walls=("N",))
        spec = DesignSpec(room=room, budget=Budget(max_inr=1_000_000))
        toilet = product("K-3814-IN-0")   # 400mm wide
        shower = product("K-706010-IN")   # 900mm wide -> together > 900mm room width
        items = [
            PlacedItem(role="primary_toilet", product=toilet),
            PlacedItem(role="primary_shower", product=shower),
        ]
        placed, violations = place_items(spec, items)
        codes = {v.code for v in violations}
        self.assertTrue(codes & {"placement_collision", "placement_out_of_room"})

    def test_layout_out_of_room(self):
        """A fixture wider than the room itself must be flagged, not
        clipped or silently placed off-canvas."""
        room = Room(width_mm=500, depth_mm=500, wet_walls=("N",))
        spec = DesignSpec(room=room, budget=Budget(max_inr=1_000_000))
        bath = product("K-K-26746-IN")  # 1500x750mm alcove bath
        items = [PlacedItem(role="primary_bath", product=bath)]
        placed, violations = place_items(spec, items)
        self.assertEqual(placed, [])
        self.assertTrue(any(v.code == "placement_out_of_room" for v in violations))

    def test_wet_wall_drain_connection_recorded(self):
        """A drain-requiring fixture placed on the wet wall must carry a
        drain connection in the Layout IR (see plan.md Layout IR spec)."""
        room = Room(width_mm=2400, depth_mm=2700, wet_walls=("N",))
        spec = DesignSpec(room=room, budget=Budget(max_inr=300_000),
                           hard_required=("toilet",))
        selected = select_candidates(spec, CATALOG)
        result = generate_design(spec, selected)
        toilet_obj = next(o for o in result["layout_ir"]["objects"] if o["category"] == "toilet")
        self.assertTrue(any(c["kind"] == "drain" for c in toilet_obj["connections"]))

    def test_compact_apt_profile_permits_what_nkba_std_rejects(self):
        """Phase 3 checklist: the constraints_profile field must
        actually change engine behavior, not just be a stored string.
        A 1200x1200mm room is too tight for any catalog toilet's front
        clearance under nkba_std (600mm) but fits under compact_apt
        (500mm) \u2014 same room, same catalog, only the profile differs.
        """
        room = Room(width_mm=1200, depth_mm=1200, wet_walls=("N",))

        nkba_spec = DesignSpec(room=room, budget=Budget(max_inr=200_000),
                                hard_required=("toilet",), constraints_profile="nkba_std")
        nkba_violations = check_hard_constraints(nkba_spec, select_candidates(nkba_spec, CATALOG))
        self.assertTrue(any(v.code == "toilet_front_clearance" for v in nkba_violations))

        compact_spec = DesignSpec(room=room, budget=Budget(max_inr=200_000),
                                   hard_required=("toilet",), constraints_profile="compact_apt")
        compact_violations = check_hard_constraints(compact_spec, select_candidates(compact_spec, CATALOG))
        self.assertFalse(any(v.code == "toilet_front_clearance" for v in compact_violations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
