"""Conversational modify + explain.

Per plan.md's "Three LLM jobs" #3: delta -> engines -> if infeasible,
structured failures + 2 alternatives; explainer writes rationale from
engine traces only, no new facts.

Store-independent (uses app.store's pure dict<->DesignSpec converters,
not the in-memory dict itself) and LLM-independent (both the intent
call and the explainer call are injected callables), so the whole
turn — extraction, repair-alternative search, explanation — is
testable without network. app/services.py is the only place that
wires in the real llm_client and the real store.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Callable

from app.ai.intent import IntentValidationError, extract_intent_delta
from app.ai.llm_client import LLMError
from app.engines.domain import DesignSpec, Product
from app.engines.recommend.itemsets import generate_top_itemsets, serialize_itemset
from app.store import spec_from_dict, spec_to_dict

_SKU_LIKE = re.compile(r"\bK-[A-Z0-9-]+\b")


def build_explanation_facts(spec_dict: dict, result: dict) -> dict:
    """Extracts exactly the facts an explanation is allowed to state —
    nothing here is inferred, only pulled straight from the engine
    output. This is the allowlist the explainer prompt is built from."""
    over_by = max(0, result["totals"]["price_inr"] - result["totals"]["budget_inr"])
    return {
        "feasible": result["feasible"],
        "items": [{"role": i["role"], "name": i["name"], "sku": i["sku"], "price_inr": i["price_inr"]}
                   for i in result["items"]],
        "total_price_inr": result["totals"]["price_inr"],
        "budget_inr": result["totals"]["budget_inr"],
        "over_budget_by_inr": over_by,
        "violations": [v["message"] for v in result["hard_violations"]],
    }


def explain_deterministic(facts: dict) -> str:
    if facts["feasible"]:
        lines = [f"This design fits your budget (\u20b9{facts['total_price_inr']:,} of "
                 f"\u20b9{facts['budget_inr']:,}) with no constraint violations."]
        for item in facts["items"]:
            lines.append(f"- {item['role'].replace('primary_', '').title()}: {item['name']} "
                         f"(\u20b9{item['price_inr']:,})")
        return "\n".join(lines)

    lines = ["This design isn't feasible yet:"]
    for msg in facts["violations"]:
        lines.append(f"- {msg}")
    if facts["over_budget_by_inr"] > 0:
        lines.append(f"Total is \u20b9{facts['over_budget_by_inr']:,} over budget.")
    return "\n".join(lines)


def explain_with_optional_llm(
    facts: dict,
    allowed_skus: set[str],
    llm_call: Callable[[str, str], str] | None = None,
) -> str:
    """Tries the LLM humanizer if one is injected; falls back to the
    deterministic template on any failure OR if the LLM's output
    mentions a SKU-like token that isn't in allowed_skus (the
    guardrail from plan.md: 'AI never invents SKUs'). This fallback
    path is what actually runs in this sandbox (no network), and it's
    also the safety net in production if the LLM ever hallucinates.
    """
    if llm_call is None:
        return explain_deterministic(facts)

    system = (
        "You explain a bathroom design result to the user in 2-4 short sentences. "
        "Use ONLY the facts given below. Do not mention any product, SKU, price, or "
        "number that is not explicitly listed. Do not invent reasons not stated."
    )
    import json as _json
    user = _json.dumps(facts, indent=2)

    try:
        text = llm_call(system, user)
    except LLMError:
        return explain_deterministic(facts)

    mentioned_skus = set(_SKU_LIKE.findall(text))
    if mentioned_skus - allowed_skus:
        return explain_deterministic(facts)  # hallucinated a SKU -> don't trust it
    return text


def _generate_for_spec(spec: DesignSpec, catalog: list[Product]) -> dict:
    """Uses the same top-itemset engine as app.services.generate (best
    of up to 3, preference-aware pooling) rather than a separate
    single-greedy path, so a chat edit and a fresh generate reach the
    same quality of pick given the same spec \u2014 e.g. 'add a rain
    shower' can actually surface a rain-shower-tagged SKU if the spec
    states that preference, not just the cheapest shower in stock."""
    itemsets = generate_top_itemsets(spec, catalog, k=1)
    if not itemsets:
        return {
            "feasible": False, "items": [], "layout_ir": {},
            "totals": {"price_inr": 0, "budget_inr": spec.budget.max_inr},
            "hard_violations": [{"code": "no_candidates",
                                  "message": "No catalog items match the required categories."}],
        }
    return serialize_itemset(itemsets[0])


def find_repair_alternatives(spec: DesignSpec, catalog: list[Product]) -> list[dict]:
    """Up to 2 alternatives, each ACTUALLY re-run through the engines
    (not just described) so 'would_be_feasible' is a verified fact,
    per plan.md: 'return minimal violating constraints... and repair
    suggestions.'
    """
    alternatives: list[dict] = []

    # Alternative 1: allow 10% budget flexibility.
    if spec.budget.flexibility != "soft_10pct":
        relaxed = replace(spec, budget=replace(spec.budget, flexibility="soft_10pct"))
        result = _generate_for_spec(relaxed, catalog)
        alternatives.append({
            "description": "Allow budget to flex 10% over the cap",
            "delta": {"budget": {"flexibility": "soft_10pct"}},
            "would_be_feasible": result["feasible"],
        })

    # Alternative 2: drop the last-listed (lowest-priority) required category.
    if len(spec.hard_required) > 1:
        trimmed = replace(spec, hard_required=spec.hard_required[:-1])
        dropped = spec.hard_required[-1]
        result = _generate_for_spec(trimmed, catalog)
        alternatives.append({
            "description": f"Drop the '{dropped}' requirement",
            "delta": {"hard_required": list(trimmed.hard_required)},
            "would_be_feasible": result["feasible"],
        })

    return alternatives[:2]


def run_chat_turn(
    spec_dict: dict,
    utterance: str,
    catalog: list[Product],
    intent_llm_call: Callable[[str, str], str],
    explainer_llm_call: Callable[[str, str], str] | None = None,
) -> dict:
    """Runs one full chat turn: extract -> merge -> re-solve -> explain
    (+ repair alternatives if infeasible). Never raises on LLM failure
    — extraction failure just means no change is applied, per the
    fail-closed guardrail (never let an unvalidated delta through).
    """
    extraction_failed = False
    try:
        delta = extract_intent_delta(utterance, spec_dict, intent_llm_call)
    except (IntentValidationError, LLMError):
        delta = {}
        extraction_failed = True

    merged_dict = dict(spec_dict)
    for key in ("room", "budget", "preferences"):
        if key in delta:
            merged_dict[key] = {**spec_dict.get(key, {}), **delta[key]}
    for key in ("hard_required", "constraints_profile"):
        if key in delta:
            merged_dict[key] = delta[key]

    spec = spec_from_dict(merged_dict)
    result = _generate_for_spec(spec, catalog)

    alternatives = [] if result["feasible"] else find_repair_alternatives(spec, catalog)
    facts = build_explanation_facts(merged_dict, result)
    allowed_skus = {p.sku for p in catalog}
    explanation = explain_with_optional_llm(facts, allowed_skus, explainer_llm_call)

    return {
        "extracted_delta": delta,
        "extraction_failed": extraction_failed,
        "spec": merged_dict,
        "generate_result": result,
        "alternatives": alternatives,
        "explanation": explanation,
    }
