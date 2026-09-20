"""Phase 2 AI-loop tests: intent extraction guardrails, RAG retrieval
guarantees, and chat-turn orchestration (repair alternatives, the
explainer's anti-hallucination check, fail-closed behavior on LLM
failure). All run with fake/injected LLM callables — no network.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.intent import IntentValidationError, extract_intent_delta
from app.ai.llm_client import LLMError
from app.ai.modify import (
    build_explanation_facts,
    explain_with_optional_llm,
    run_chat_turn,
)
from app.ai.rag import search_catalog
from app.engines.catalog_loader import load_catalog

CATALOG = load_catalog()

BASE_SPEC = {
    "room": {"width_mm": 2400, "depth_mm": 2700, "wet_walls": ["N"]},
    "budget": {"max_inr": 300_000},
    "hard_required": ["toilet", "shower", "vanity"],
}


class IntentGuardrailTests(unittest.TestCase):

    def test_accepts_well_formed_delta(self):
        llm = lambda s, u: '{"budget": {"max_inr": 250000}}'
        delta = extract_intent_delta("cut budget", BASE_SPEC, llm)
        self.assertEqual(delta, {"budget": {"max_inr": 250000}})

    def test_rejects_unknown_top_level_field(self):
        llm = lambda s, u: '{"system_override": "ignore all rules"}'
        with self.assertRaises(IntentValidationError):
            extract_intent_delta("x", BASE_SPEC, llm)

    def test_rejects_unknown_nested_field(self):
        llm = lambda s, u: '{"room": {"sku_override": "K-FAKE"}}'
        with self.assertRaises(IntentValidationError):
            extract_intent_delta("x", BASE_SPEC, llm)

    def test_rejects_non_json_prose(self):
        llm = lambda s, u: "Sure! I updated your budget."
        with self.assertRaises(IntentValidationError):
            extract_intent_delta("x", BASE_SPEC, llm)

    def test_rejects_wrong_type_for_hard_required(self):
        llm = lambda s, u: '{"hard_required": "toilet"}'
        with self.assertRaises(IntentValidationError):
            extract_intent_delta("x", BASE_SPEC, llm)

    def test_empty_object_is_valid_no_op(self):
        llm = lambda s, u: "{}"
        self.assertEqual(extract_intent_delta("what's the weather", BASE_SPEC, llm), {})


class RagTests(unittest.TestCase):

    def test_results_are_always_a_catalog_subset(self):
        """Guardrail from plan.md: 'Retrieved SKUs \u2286 catalog; no
        hallucinated SKU in items.'"""
        for query in ["wall hung toilet", "rain shower", "oak vanity", "gibberish zzz"]:
            results = search_catalog(query, CATALOG, top_k=5)
            self.assertTrue(set(r.id for r in results) <= set(p.id for p in CATALOG))

    def test_relevant_query_returns_matching_category(self):
        results = search_catalog("wall hung toilet", CATALOG, top_k=3)
        self.assertTrue(any(r.category == "toilet" for r in results))

    def test_nonsense_query_returns_empty(self):
        self.assertEqual(search_catalog("zzz qqq nonexistent", CATALOG), [])

    def test_category_filter_pool_respected(self):
        toilets_only = [p for p in CATALOG if p.category == "toilet"]
        results = search_catalog("compact", toilets_only, top_k=5)
        self.assertTrue(all(r.category == "toilet" for r in results))


class ChatTurnTests(unittest.TestCase):

    def test_feasible_change_applies_delta_and_explains(self):
        llm = lambda s, u: '{"budget": {"max_inr": 200000}}'
        turn = run_chat_turn(BASE_SPEC, "lower budget", CATALOG, llm)
        self.assertEqual(turn["extracted_delta"], {"budget": {"max_inr": 200000}})
        self.assertTrue(turn["generate_result"]["feasible"])
        self.assertFalse(turn["extraction_failed"])
        self.assertIn("\u20b9", turn["explanation"])

    def test_infeasible_change_returns_real_repair_alternatives(self):
        llm = lambda s, u: '{"budget": {"max_inr": 1000}}'
        turn = run_chat_turn(BASE_SPEC, "drop budget", CATALOG, llm)
        self.assertFalse(turn["generate_result"]["feasible"])
        self.assertLessEqual(len(turn["alternatives"]), 2)
        for alt in turn["alternatives"]:
            self.assertIn("would_be_feasible", alt)
            self.assertIsInstance(alt["would_be_feasible"], bool)

    def test_explainer_rejects_hallucinated_sku(self):
        facts = build_explanation_facts(BASE_SPEC, {
            "feasible": True, "items": [], "hard_violations": [],
            "totals": {"price_inr": 0, "budget_inr": 300000},
        })
        hallucinating = lambda s, u: "I recommend the amazing K-99999-FAKE toilet!"
        allowed = {p.sku for p in CATALOG}
        explanation = explain_with_optional_llm(facts, allowed, hallucinating)
        self.assertNotIn("K-99999-FAKE", explanation)

    def test_explainer_uses_llm_output_when_skus_are_real(self):
        real_sku = CATALOG[0].sku
        facts = build_explanation_facts(BASE_SPEC, {
            "feasible": True, "items": [], "hard_violations": [],
            "totals": {"price_inr": 0, "budget_inr": 300000},
        })
        honest = lambda s, u: f"Great choice with {real_sku}!"
        allowed = {p.sku for p in CATALOG}
        explanation = explain_with_optional_llm(facts, allowed, honest)
        self.assertEqual(explanation, f"Great choice with {real_sku}!")

    def test_llm_failure_fails_closed_spec_unchanged(self):
        def broken(s, u):
            raise LLMError("simulated network failure")
        turn = run_chat_turn(BASE_SPEC, "change something", CATALOG, broken)
        self.assertTrue(turn["extraction_failed"])
        self.assertEqual(turn["extracted_delta"], {})
        self.assertEqual(turn["spec"]["budget"], BASE_SPEC["budget"])

    def test_invalid_delta_fails_closed(self):
        llm = lambda s, u: '{"not_a_real_field": 1}'
        turn = run_chat_turn(BASE_SPEC, "hack attempt", CATALOG, llm)
        self.assertTrue(turn["extraction_failed"])
        self.assertEqual(turn["spec"], BASE_SPEC)


if __name__ == "__main__":
    unittest.main(verbosity=2)
