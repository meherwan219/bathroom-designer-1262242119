"""Thin client for the Anthropic Messages API.

Isolated in one module so every other AI module (intent, rag, modify)
depends only on a `Callable[[str, str], str]` signature (system, user
-> raw text response) and never imports httpx directly. That's what
makes them unit-testable without network: tests inject a fake
callable instead of this one.

Not exercised by any test in this repo — this sandbox has no network
access to verify a real call. The guardrail/validation logic that
consumes its output (app/ai/intent.py, app/ai/modify.py) IS tested,
against both well-formed and adversarial fake responses.
"""
from __future__ import annotations

import json

from app.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(Exception):
    pass


def complete(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
    """Single-turn completion. Raises LLMError on any failure (missing
    key, network error, non-2xx, malformed response) so callers can
    apply a deterministic fallback instead of crashing the request.

    httpx is imported lazily so every other module that only needs the
    LLMError type (for except clauses) doesn't require httpx to be
    installed just to import this module.
    """
    if not settings.llm_api_key or settings.llm_api_key == "changeme":
        raise LLMError("LLM_API_KEY is not configured")

    try:
        import httpx
    except ImportError as e:
        raise LLMError("httpx is not installed") from e

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
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        if not blocks:
            raise LLMError("LLM response had no text content")
        return "".join(blocks)
    except httpx.HTTPError as e:
        raise LLMError(f"LLM request failed: {e}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise LLMError(f"LLM response malformed: {e}") from e
