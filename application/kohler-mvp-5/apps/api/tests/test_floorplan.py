"""Phase 4 vision/floor-plan tests, per plan.md: "floor-plan image ->
bounding box + door candidates. User confirms dimensions in UI. Never
auto-trust pixels for hard constraints." All run with fake vision
callables \u2014 no network, no real image needed (validation never
decodes image content, only forwards it).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import services
from app.ai.floorplan import FloorplanValidationError, extract_floorplan
from app.ai.llm_client import LLMError

FAKE_IMAGE_B64 = "ZmFrZQ=="  # base64("fake") - never decoded as a real image, just forwarded


class FloorplanGuardrailTests(unittest.TestCase):

    def test_accepts_well_formed_proposal(self):
        good = lambda s, u, img: '{"width_mm": 2400, "depth_mm": 2700, "confidence": 0.72}'
        result = extract_floorplan(FAKE_IMAGE_B64, good)
        self.assertEqual(result["width_mm"], 2400)
        self.assertEqual(result["confidence"], 0.72)

    def test_rejects_implausible_dimension(self):
        huge = lambda s, u, img: '{"width_mm": 24000, "depth_mm": 2700, "confidence": 0.5}'
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, huge)

    def test_rejects_too_small_dimension(self):
        tiny = lambda s, u, img: '{"width_mm": 50, "depth_mm": 2700, "confidence": 0.5}'
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, tiny)

    def test_rejects_out_of_range_confidence(self):
        bad = lambda s, u, img: '{"width_mm": 2400, "depth_mm": 2700, "confidence": 1.5}'
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, bad)

    def test_rejects_unknown_injected_field(self):
        """The interesting adversarial case for this endpoint: a
        vision response trying to sneak in a field that would make the
        proposal look self-applying."""
        inject = lambda s, u, img: (
            '{"width_mm": 2400, "depth_mm": 2700, "confidence": 0.8, "apply_immediately": true}'
        )
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, inject)

    def test_rejects_bad_door_wall_value(self):
        bad_door = lambda s, u, img: (
            '{"width_mm": 2400, "depth_mm": 2700, "confidence": 0.8, '
            '"doors": [{"wall": "NE", "offset_mm": 0, "width_mm": 700}]}'
        )
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, bad_door)

    def test_rejects_non_json_prose(self):
        prose = lambda s, u, img: "This looks like roughly a 2.4 by 2.7 meter bathroom."
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, prose)

    def test_rejects_missing_required_field(self):
        missing = lambda s, u, img: '{"width_mm": 2400, "confidence": 0.8}'
        with self.assertRaises(FloorplanValidationError):
            extract_floorplan(FAKE_IMAGE_B64, missing)

    def test_low_confidence_still_accepted_as_a_draft(self):
        """A low-confidence read is still a valid DRAFT \u2014 confidence is
        informational for the UI, not itself a pass/fail gate here."""
        low_conf = lambda s, u, img: '{"width_mm": 2000, "depth_mm": 2000, "confidence": 0.15}'
        result = extract_floorplan(FAKE_IMAGE_B64, low_conf)
        self.assertEqual(result["confidence"], 0.15)


class FloorplanNeverPersistsTests(unittest.TestCase):
    """The architectural guarantee: floorplan_proposal cannot write to
    any design's spec, because it never touches app.store at all."""

    def test_floorplan_proposal_takes_no_design_id(self):
        import inspect
        sig = inspect.signature(services.floorplan_proposal)
        self.assertNotIn("design_id", sig.parameters)

    def test_floorplan_proposal_module_does_not_import_store_write_path(self):
        import app.ai.floorplan as fp_module
        self.assertFalse(hasattr(fp_module, "store"))

    def test_fails_closed_without_api_key_no_crash(self):
        """This repo's default LLM_API_KEY is unset, so this exercises
        the REAL vision_client path (not a fake), proving the fail-
        closed behavior end-to-end, not just in the injected-fake tests
        above."""
        result = services.floorplan_proposal(FAKE_IMAGE_B64)
        self.assertIsNone(result["proposal"])
        self.assertIsNotNone(result["error"])

    def test_valid_fake_response_returns_proposal_not_a_design(self):
        import app.services as services_module
        original = services_module.vision_client.complete_with_image
        services_module.vision_client.complete_with_image = (
            lambda s, u, img, media_type="image/jpeg", max_tokens=1024:
            '{"width_mm": 2400, "depth_mm": 2700, "confidence": 0.9}'
        )
        try:
            result = services.floorplan_proposal(FAKE_IMAGE_B64)
        finally:
            services_module.vision_client.complete_with_image = original

        self.assertIsNotNone(result["proposal"])
        self.assertNotIn("id", result)          # no design was created
        self.assertNotIn("status", result)      # not a design record shape


if __name__ == "__main__":
    unittest.main(verbosity=2)
