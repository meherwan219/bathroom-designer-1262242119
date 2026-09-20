"""Phase 1 design store: in-memory, process-lifetime only.

The DB schema in plan.md (designs, design_items tables) is the real
target, but this sandbox has no live Postgres to persist against, and
an untested SQLAlchemy wiring is worse than an honest stopgap. This
module is the single seam to swap: replace `_DESIGNS` with real
session.query(Design) calls and nothing above the router needs to
change, since callers only see spec_from_dict / spec_to_dict / the
dict-based get/set below.

Also stdlib-only (uuid + dataclasses.replace), so it stays unit-testable.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from app.engines.domain import Budget, DesignSpec, Door, Preferences, Room

_DESIGNS: dict[str, dict[str, Any]] = {}


def spec_from_dict(d: dict) -> DesignSpec:
    """Converts an intake-form JSON payload into a DesignSpec.

    Expected shape:
        {
          "room": {"width_mm": int, "depth_mm": int, "height_mm"?: int,
                    "doors"?: [{"id","wall","offset_mm","width_mm","swing"?}],
                    "wet_walls"?: ["N", ...]},
          "budget": {"max_inr": int, "flexibility"?: "none"|"soft_10pct"},
          "hard_required": ["toilet","vanity",...],
          "preferences"?: {"styles"?: [...], "features"?: [...],
                            "sustainability_weight"?: float,
                            "space_efficiency_weight"?: float},
          "constraints_profile"?: "nkba_std" | "compact_apt"
        }
    """
    room_d = d.get("room", {})
    doors = tuple(
        Door(id=door["id"], wall=door["wall"], offset_mm=door["offset_mm"],
             width_mm=door["width_mm"], swing=door.get("swing", "in"))
        for door in room_d.get("doors", [])
    )
    room = Room(
        width_mm=room_d["width_mm"],
        depth_mm=room_d["depth_mm"],
        height_mm=room_d.get("height_mm", 2400),
        doors=doors,
        wet_walls=tuple(room_d.get("wet_walls", ["N"])),
    )
    budget_d = d.get("budget", {})
    budget = Budget(
        max_inr=budget_d.get("max_inr", 0),
        flexibility=budget_d.get("flexibility", "none"),
    )
    prefs_d = d.get("preferences", {})
    prefs = Preferences(
        styles=tuple(prefs_d.get("styles", [])),
        features=tuple(prefs_d.get("features", [])),
        sustainability_weight=prefs_d.get("sustainability_weight", 0.2),
        space_efficiency_weight=prefs_d.get("space_efficiency_weight", 0.15),
    )
    return DesignSpec(
        room=room,
        budget=budget,
        hard_required=tuple(d.get("hard_required", [])),
        preferences=prefs,
        constraints_profile=d.get("constraints_profile", "nkba_std"),
    )


def spec_to_dict(spec: DesignSpec) -> dict:
    return {
        "room": {
            "width_mm": spec.room.width_mm,
            "depth_mm": spec.room.depth_mm,
            "height_mm": spec.room.height_mm,
            "doors": [
                {"id": dr.id, "wall": dr.wall, "offset_mm": dr.offset_mm,
                 "width_mm": dr.width_mm, "swing": dr.swing}
                for dr in spec.room.doors
            ],
            "wet_walls": list(spec.room.wet_walls),
        },
        "budget": {"max_inr": spec.budget.max_inr, "flexibility": spec.budget.flexibility},
        "hard_required": list(spec.hard_required),
        "preferences": {
            "styles": list(spec.preferences.styles),
            "features": list(spec.preferences.features),
            "sustainability_weight": spec.preferences.sustainability_weight,
            "space_efficiency_weight": spec.preferences.space_efficiency_weight,
        },
        "constraints_profile": spec.constraints_profile,
    }


def create(spec_payload: dict) -> dict:
    design_id = str(uuid.uuid4())
    spec = spec_from_dict(spec_payload)
    record = {"id": design_id, "status": "draft", "spec": spec, "last_result": None}
    _DESIGNS[design_id] = record
    return record


def get(design_id: str) -> dict | None:
    return _DESIGNS.get(design_id)


def update_spec(design_id: str, patch: dict) -> dict | None:
    record = _DESIGNS.get(design_id)
    if record is None:
        return None
    current = spec_to_dict(record["spec"])
    # shallow-merge top-level keys; nested dicts (room/budget/preferences)
    # are replaced wholesale if present in the patch, per PATCH semantics
    current.update(patch)
    record["spec"] = spec_from_dict(current)
    record["status"] = "draft"
    return record


def replace_spec(design_id: str, spec_dict: dict) -> dict | None:
    """Wholesale spec replacement — used after app.ai.modify.run_chat_turn
    has already computed the fully-merged spec, so it should not be
    merged again on top of the (now-stale) stored spec."""
    record = _DESIGNS.get(design_id)
    if record is None:
        return None
    record["spec"] = spec_from_dict(spec_dict)
    return record


def set_result(design_id: str, result: dict, status: str) -> None:
    record = _DESIGNS.get(design_id)
    if record is not None:
        record["last_result"] = result
        record["status"] = status
