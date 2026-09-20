"""Vision-assisted floor-plan extraction: image -> proposed room
polygon + door candidates (plan.md: "Vision (optional, phase 2):
floor-plan image -> bounding box + door candidates. User confirms
dimensions in UI. Never auto-trust pixels for hard constraints.")

The core guardrail is architectural, not just validation: this module
only ever returns a *proposal* dict. Nothing in this file, and nothing
in app/services.py's floorplan_proposal(), writes to app/store.py or
touches a DesignSpec. The proposal reaches a real spec only if the
user explicitly submits it back through the ordinary
PATCH /designs/{id}/spec path \u2014 the exact same validated path manual
form input goes through. A vision proposal gets no special privilege
over a typed-in number.

Schema validation (this IS tested, with fake vision responses,
including adversarial ones \u2014 see tests/test_floorplan.py):
  - reject anything that isn't well-formed JSON
  - reject unknown fields
  - reject out-of-range confidence (must be in [0, 1])
  - reject physically implausible dimensions (a proposed room outside
    500-10000mm on either axis is almost certainly a misread, not a
    tiny or a warehouse-sized bathroom)
"""
from __future__ import annotations

import json
from typing import Callable

SYSTEM_PROMPT = """You analyze a photo of a bathroom floor plan sketch or blueprint.

Output ONLY a JSON object (no markdown, no commentary) with this exact shape:
{
  "width_mm": <int>,
  "depth_mm": <int>,
  "doors": [{"wall": "N"|"S"|"E"|"W", "offset_mm": <int>, "width_mm": <int>}],
  "confidence": <float between 0 and 1>
}

If you cannot make out clear dimensions, use your best estimate and set confidence
low (below 0.4) rather than omitting fields. Do not add any field not listed above.
This is a DRAFT the user will review and correct \u2014 approximate but honest
confidence matters more than precision.
"""

MIN_DIM_MM = 500
MAX_DIM_MM = 10_000
ALLOWED_TOP_LEVEL = {"width_mm", "depth_mm", "doors", "confidence"}
ALLOWED_DOOR_FIELDS = {"wall", "offset_mm", "width_mm"}


class FloorplanValidationError(Exception):
    pass


def _validate_proposal(proposal: dict) -> dict:
    if not isinstance(proposal, dict):
        raise FloorplanValidationError("proposal must be a JSON object")

    unknown = set(proposal.keys()) - ALLOWED_TOP_LEVEL
    if unknown:
        raise FloorplanValidationError(f"unknown field(s): {sorted(unknown)}")

    required = {"width_mm", "depth_mm", "confidence"}
    missing = required - set(proposal.keys())
    if missing:
        raise FloorplanValidationError(f"missing required field(s): {sorted(missing)}")

    for dim_key in ("width_mm", "depth_mm"):
        val = proposal[dim_key]
        if not isinstance(val, int) or isinstance(val, bool):
            raise FloorplanValidationError(f"'{dim_key}' must be an integer")
        if not (MIN_DIM_MM <= val <= MAX_DIM_MM):
            raise FloorplanValidationError(
                f"'{dim_key}'={val} is outside the plausible range "
                f"[{MIN_DIM_MM}, {MAX_DIM_MM}]mm"
            )

    conf = proposal["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0.0 <= conf <= 1.0):
        raise FloorplanValidationError("'confidence' must be a number in [0, 1]")

    doors = proposal.get("doors", [])
    if not isinstance(doors, list):
        raise FloorplanValidationError("'doors' must be an array")
    for door in doors:
        if not isinstance(door, dict):
            raise FloorplanValidationError("each door must be an object")
        unknown_door = set(door.keys()) - ALLOWED_DOOR_FIELDS
        if unknown_door:
            raise FloorplanValidationError(f"unknown door field(s): {sorted(unknown_door)}")
        if door.get("wall") not in ("N", "S", "E", "W"):
            raise FloorplanValidationError("door 'wall' must be one of N/S/E/W")

    return proposal


def build_user_prompt() -> str:
    return "Extract the room dimensions and door positions from this floor plan image."


def extract_floorplan(
    image_base64: str,
    vision_call: Callable[[str, str, str], str],
) -> dict:
    """vision_call is injected as (system, user_text, image_base64) ->
    raw_text, so this is testable without network or a real image \u2014
    pass a fake that returns canned JSON, including malformed/
    adversarial ones, to prove the guardrail rejects them.

    Returns the validated proposal dict. Raises
    FloorplanValidationError on anything non-conforming. Callers
    (app.services.floorplan_proposal) must catch this and surface a
    clear "couldn't read the image" response \u2014 never a partial or
    best-guess spec applied silently.
    """
    raw = vision_call(SYSTEM_PROMPT, build_user_prompt(), image_base64)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise FloorplanValidationError(f"vision model did not return valid JSON: {e}") from e
    return _validate_proposal(parsed)
