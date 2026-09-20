"""Loads the product_compat graph (see plan.md's `product_compat` table:
`product_id`, `other_id`, `relation`, `notes`) from the seed JSON.
Stdlib-only, same pattern as catalog_loader.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COMPAT_PATH = Path(__file__).resolve().parents[1] / "seed" / "product_compat.json"


@dataclass(frozen=True)
class CompatRule:
    product_id: str
    other_id: str
    relation: str  # "requires" | "incompatible" | "finish_match" | "rough_in_match"
    notes: str = ""


def load_compat_rules(path: Path = DEFAULT_COMPAT_PATH) -> list[CompatRule]:
    raw = json.loads(path.read_text())
    return [CompatRule(**r) for r in raw]
