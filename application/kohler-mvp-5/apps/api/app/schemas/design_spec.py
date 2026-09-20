"""Canonical Design Spec contract (form + intent-LLM output).

Kept separate from SQLAlchemy models: this is the wire/JSON shape,
not the storage shape.
"""
from pydantic import BaseModel, Field


class Door(BaseModel):
    id: str
    wall: str
    offset_mm: int
    width_mm: int
    swing: str


class Room(BaseModel):
    width_mm: int
    depth_mm: int
    height_mm: int
    doors: list[Door] = Field(default_factory=list)
    windows: list[dict] = Field(default_factory=list)
    wet_wall_hint: str | None = None


class Budget(BaseModel):
    max: int
    currency: str = "INR"
    flexibility: str = "none"


class Preferences(BaseModel):
    styles: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    sustainability_weight: float = 0.2
    space_efficiency_weight: float = 0.15


class DesignSpec(BaseModel):
    room: Room
    budget: Budget
    hard_required: list[str] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)
    constraints_profile: str = "nkba_std"


class DesignSpecDelta(BaseModel):
    """Partial update produced by the intent LLM. All fields optional;
    unknown fields are rejected by pydantic's default strict parsing."""

    room: dict | None = None
    budget: dict | None = None
    hard_required: list[str] | None = None
    preferences: dict | None = None
    constraints_profile: str | None = None
