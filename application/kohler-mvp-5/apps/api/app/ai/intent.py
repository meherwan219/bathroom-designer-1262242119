"""Intent extraction: utterance -> DesignSpecDelta.

Per plan.md's "Three LLM jobs" #1: map an utterance to a strict-schema
delta at temperature ~0, reject unknown fields. This module owns the
guardrail (schema validation), not just the prompt — an LLM that
returns an extra field, a wrong type, or non-JSON must never reach
the engines. That's tested here with fake LLM responses, including
adversarial ones, with zero network required.
"""
from __future__ import annotations

import json
from typing import Callable

SYSTEM_PROMPT = """You extract structured edits from a bathroom design chat message.

Given the user's message and the CURRENT design spec (JSON), output ONLY a JSON
object representing the CHANGES the user wants — a DesignSpecDelta. Do not repeat
unchanged fields. Do not add commentary, markdown fences, or any text outside the
JSON object.

Allowed top-level keys (all optional): room, budget, hard_required, preferences,
constraints_profile. Do not invent any other key.

  room: {width_mm?, depth_mm?, height_mm?, wet_walls?}
  budget: {max_inr?, flexibility?}          flexibility is "none" or "soft_10pct"
  hard_required: string[]                    product categories or exact SKUs
  preferences: {styles?, features?, sustainability_weight?, space_efficiency_weight?}
  constraints_profile: "nkba_std" or "compact_apt"

If the message requests something outside this schema (e.g. a specific brand not
in context, a room feature with no field), omit it — never invent a field to fit it.
If the message isn't a design change at all, return {}.
"""

ALLOWED_TOP_LEVEL = {"room", "budget", "hard_required", "preferences", "constraints_profile"}
ALLOWED_NESTED = {
    "room": {"width_mm", "depth_mm", "height_mm", "wet_walls"},
    "budget": {"max_inr", "flexibility"},
    "preferences": {"styles", "features", "sustainability_weight", "space_efficiency_weight"},
}


class IntentValidationError(Exception):
    """Raised when the LLM's output doesn't conform to the delta schema."""


def _validate_delta(delta: dict) -> dict:
    if not isinstance(delta, dict):
        raise IntentValidationError("delta must be a JSON object")

    unknown_top = set(delta.keys()) - ALLOWED_TOP_LEVEL
    if unknown_top:
        raise IntentValidationError(f"unknown top-level field(s): {sorted(unknown_top)}")

    for key, allowed_children in ALLOWED_NESTED.items():
        if key in delta:
            if not isinstance(delta[key], dict):
                raise IntentValidationError(f"'{key}' must be an object")
            unknown_nested = set(delta[key].keys()) - allowed_children
            if unknown_nested:
                raise IntentValidationError(f"unknown field(s) in '{key}': {sorted(unknown_nested)}")

    if "hard_required" in delta and not isinstance(delta["hard_required"], list):
        raise IntentValidationError("'hard_required' must be an array")

    if "constraints_profile" in delta and delta["constraints_profile"] not in ("nkba_std", "compact_apt"):
        raise IntentValidationError("'constraints_profile' must be 'nkba_std' or 'compact_apt'")

    return delta


def build_user_prompt(utterance: str, current_spec: dict) -> str:
    return (
        f"CURRENT SPEC:\n{json.dumps(current_spec, indent=2)}\n\n"
        f"USER MESSAGE:\n{utterance}"
    )


def extract_intent_delta(
    utterance: str,
    current_spec: dict,
    llm_call: Callable[[str, str], str],
) -> dict:
    """Runs intent extraction and validates the result.

    llm_call is injected (system, user) -> raw_text so this is testable
    without network: pass a fake that returns canned JSON strings,
    including malformed ones, to prove the guardrail actually rejects
    them rather than passing them through to the engines.

    Raises IntentValidationError on anything that doesn't conform —
    callers (app.ai.modify) must catch this and fall back gracefully,
    never let an unvalidated delta reach app.store.update_spec.
    """
    raw = llm_call(SYSTEM_PROMPT, build_user_prompt(utterance, current_spec))
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise IntentValidationError(f"LLM did not return valid JSON: {e}") from e
    return _validate_delta(parsed)
