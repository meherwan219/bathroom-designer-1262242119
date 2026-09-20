"""Layout engine.

Places PlacedItems on a grid inside the room, snapping drain-requiring
fixtures to a wet wall, and rejects placements that collide. Produces
the Layout IR document described in plan.md (units: mm).

Placement heuristic (feasible > optimal, per plan.md solver strategy):
  1. Items requiring a drain go along the first configured wet wall,
     left to right, in slot order (toilet, shower/bath, vanity).
  2. Remaining items go along the opposite wall.
  3. Anything that would collide with an already-placed item, or spill
     outside the room, is reported as a collision violation instead of
     being silently placed — the validator rejects the whole design.
"""
from __future__ import annotations

from app.engines.domain import DesignSpec, PlacedItem, Violation

GRID_MM = 25
WALL_ORDER = ("N", "S", "E", "W")


def _snap(v: int) -> int:
    return round(v / GRID_MM) * GRID_MM


def _rect_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def place_items(spec: DesignSpec, items: list[PlacedItem]) -> tuple[list[PlacedItem], list[Violation]]:
    """Returns (placed_items_with_xy, collision_violations)."""
    room = spec.room
    wet_wall = spec.room.wet_walls[0] if spec.room.wet_walls else "N"

    wet_items = [i for i in items if i.product.requires_drain]
    dry_items = [i for i in items if not i.product.requires_drain]

    placed: list[PlacedItem] = []
    occupied: list[tuple[int, int, int, int]] = []
    violations: list[Violation] = []

    def place_row(row_items: list[PlacedItem], along_wall: str) -> None:
        cursor = 0
        for item in row_items:
            p = item.product
            w, d = _snap(p.width_mm), _snap(p.depth_mm)

            if along_wall in ("N", "S"):
                x, y = cursor, 0 if along_wall == "N" else room.depth_mm - d
            else:
                x, y = 0 if along_wall == "W" else room.width_mm - d, cursor

            rect = (x, y, x + w, y + d)

            if x + w > room.width_mm or y + d > room.depth_mm or x < 0 or y < 0:
                violations.append(Violation(
                    code="placement_out_of_room",
                    message=f"{p.name} does not fit along wall {along_wall} "
                            f"in a {room.width_mm}x{room.depth_mm}mm room.",
                ))
                continue

            if any(_rect_overlap(rect, other) for other in occupied):
                violations.append(Violation(
                    code="placement_collision",
                    message=f"{p.name} overlaps another fixture along wall {along_wall}.",
                ))
                continue

            occupied.append(rect)
            placed.append(PlacedItem(role=item.role, product=p, x_mm=x, y_mm=y, rotation_deg=0))
            cursor += w if along_wall in ("N", "S") else d

    place_row(wet_items, wet_wall)
    other_wall = "S" if wet_wall == "N" else "N" if wet_wall == "S" else ("W" if wet_wall == "E" else "E")
    place_row(dry_items, other_wall)

    return placed, violations


def to_layout_ir(spec: DesignSpec, placed_items: list[PlacedItem], solver_version: str = "0.1.0") -> dict:
    """Serializes placed items into the Layout IR JSON shape from plan.md."""
    room = spec.room
    return {
        "units": "mm",
        "room": {
            "polygon": [[0, 0], [room.width_mm, 0], [room.width_mm, room.depth_mm], [0, room.depth_mm]],
            "height_mm": room.height_mm,
            "doors": [
                {"id": dr.id, "wall": dr.wall, "offset": dr.offset_mm, "width": dr.width_mm, "swing": dr.swing}
                for dr in room.doors
            ],
            "windows": [],
        },
        "wet_walls": list(room.wet_walls),
        "grid_mm": GRID_MM,
        "objects": [
            {
                "id": f"{item.role}-{item.product.id}",
                "sku": item.product.sku,
                "category": item.product.category,
                "role": item.role,
                "finish": item.product.finish,
                "origin": {"x": item.x_mm, "y": item.y_mm},
                "rotation_deg": item.rotation_deg,
                "bbox": {"w": item.product.width_mm, "d": item.product.depth_mm, "h": item.product.height_mm},
                "clearances": [],
                "connections": (
                    [{"kind": "drain", "wall_id": spec.room.wet_walls[0]}]
                    if item.product.requires_drain and spec.room.wet_walls else []
                ),
            }
            for item in placed_items
        ],
        "circulation": [],
        "meta": {"profile": spec.constraints_profile, "solver_version": solver_version, "seed": 0},
    }
