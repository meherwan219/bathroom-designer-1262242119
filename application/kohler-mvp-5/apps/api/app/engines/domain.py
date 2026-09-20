"""Shared domain types for the engines.

Deliberately dependency-free (stdlib dataclasses only, no pydantic/
FastAPI import) so every engine unit-tests in isolation, per plan.md:
"Keep engines as pure Python modules with no FastAPI imports."
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Door:
    id: str
    wall: str  # "N" | "S" | "E" | "W"
    offset_mm: int
    width_mm: int
    swing: str = "in"  # "in" | "out"


@dataclass(frozen=True)
class Room:
    width_mm: int   # along the E-W axis (x)
    depth_mm: int   # along the N-S axis (y)
    height_mm: int = 2400
    doors: tuple[Door, ...] = ()
    wet_walls: tuple[str, ...] = ("N",)  # which wall(s) carry drains/supply


@dataclass(frozen=True)
class Budget:
    max_inr: int
    flexibility: str = "none"  # "none" | "soft_10pct"


@dataclass(frozen=True)
class Preferences:
    styles: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    sustainability_weight: float = 0.2
    space_efficiency_weight: float = 0.15


@dataclass(frozen=True)
class DesignSpec:
    room: Room
    budget: Budget
    hard_required: tuple[str, ...] = ()  # e.g. ("toilet", "vanity", "shower")
    preferences: Preferences = field(default_factory=Preferences)
    constraints_profile: str = "nkba_std"


@dataclass(frozen=True)
class Product:
    """Mirrors a row of app/seed/products.json."""
    id: str
    sku: str
    name: str
    category: str
    family: str
    collection: str
    width_mm: int
    depth_mm: int
    height_mm: int
    price_inr: int
    install_type: str
    water_use: float | None
    finish: str
    style_tags: tuple[str, ...]
    sustainability_score: int
    requires_supply: bool
    requires_drain: bool
    clearance_overrides: dict
    is_active: bool = True

    @staticmethod
    def from_json(d: dict) -> "Product":
        return Product(
            id=d["id"], sku=d["sku"], name=d["name"], category=d["category"],
            family=d.get("family", ""), collection=d.get("collection", ""),
            width_mm=d["width_mm"], depth_mm=d["depth_mm"], height_mm=d["height_mm"],
            price_inr=d["price_inr"], install_type=d.get("install_type", "floor"),
            water_use=d.get("water_use"), finish=d.get("finish", ""),
            style_tags=tuple(d.get("style_tags", [])),
            sustainability_score=d.get("sustainability_score", 50),
            requires_supply=bool(d.get("requires_supply", False)),
            requires_drain=bool(d.get("requires_drain", False)),
            clearance_overrides=d.get("clearance_overrides", {}) or {},
            is_active=d.get("is_active", True),
        )


@dataclass(frozen=True)
class PlacedItem:
    """A product assigned to a design slot, before/after placement."""
    role: str        # "primary_toilet" | "primary_vanity" | "primary_faucet" | ...
    product: Product
    x_mm: int | None = None
    y_mm: int | None = None
    rotation_deg: int = 0


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    severity: str = "hard"  # "hard" | "soft"


# Category -> design slot role, and which roles hard_required strings map to.
SLOT_TO_CATEGORY = {
    "toilet": "toilet",
    "vanity": "vanity",
    "faucet": "faucet",
    "shower": "shower",
    "bath": "bath",
    "storage": "storage",
}
