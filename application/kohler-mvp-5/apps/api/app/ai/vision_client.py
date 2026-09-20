"""Vision-capable completion, for the floor-plan confirm flow.

Same isolation pattern as app.ai.llm_client: one function, lazy httpx
import, raises VisionError on any failure so callers apply a
deterministic "vision unavailable" fallback instead of crashing.
Never exercised against real network in this sandbox \u2014 see
app/ai/floorplan.py's docstring for what IS tested (the guardrail
that consumes this function's output).
"""
from __future__ import annotations

import json

from app.config import settings
from app.ai.llm_client import ANTHROPIC_API_URL, ANTHROPIC_VERSION, LLMError


class VisionError(LLMError):
    pass


def complete_with_image(system: str, user_text: str, image_base64: str, media_type: str = "image/jpeg",
                         max_tokens: int = 1024) -> str:
    """Single-turn completion with one image attached. Raises
    VisionError on any failure (missing key, network error, non-2xx,
    malformed response, or image data that isn't valid base64)."""
    if not settings.llm_api_key or settings.llm_api_key == "changeme":
        raise VisionError("LLM_API_KEY is not configured")

    try:
        import base64 as _b64
        _b64.b64decode(image_base64, validate=True)
    except Exception as e:
        raise VisionError(f"image_base64 is not valid base64: {e}") from e

    try:
        import httpx
    except ImportError as e:
        raise VisionError("httpx is not installed") from e

    try:
        resp = httpx.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": settings.llm_api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": max_tokens,
                "temperature": 0.0,
                "system": system,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                        {"type": "text", "text": user_text},
                    ],
                }],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        if not blocks:
            raise VisionError("vision response had no text content")
        return "".join(blocks)
    except httpx.HTTPError as e:
        raise VisionError(f"vision request failed: {e}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise VisionError(f"vision response malformed: {e}") from e
