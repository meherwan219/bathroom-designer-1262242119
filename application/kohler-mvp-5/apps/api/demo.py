#!/usr/bin/env python3
"""Scripted demo path, per plan.md's Phase 5: "one scripted demo path
(small Indian apartment, tight budget, eco preference, then 'add rain
shower' infeasible -> repair)."

Runs the exact same code path a live request would (app.services,
app.ai.modify) with no server needed \u2014 useful both as a live demo
narration script and as an executable proof that the numbers in
README's demo walkthrough are real, not invented. Run it:

    cd apps/api && python3 demo.py

The chat step's intent extraction is simulated (see the inline note)
since this environment has no network/LLM_API_KEY \u2014 the simulated
delta is exactly what a correct real extraction would produce for
"add a rain shower", validated through the same guardrail a live
call goes through.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import services, store
from app.ai.modify import run_chat_turn
from app.engines.catalog_loader import load_catalog


def rule():
    print("-" * 72)


def money(n: int) -> str:
    return f"\u20b9{n:,}"


def show_result(label: str, result: dict) -> None:
    feasible = result.get("feasible", len(result["hard_violations"]) == 0)
    print(f"{label}: {'FEASIBLE' if feasible else 'INFEASIBLE'}")
    for item in result["items"]:
        print(f"  - {item['role'].replace('primary_', '').replace('required_', '+').title()}: "
              f"{item['name']} ({money(item['price_inr'])})")
    print(f"  Total: {money(result['totals']['price_inr'])} / "
          f"Budget: {money(result['totals']['budget_inr'])}")
    for v in result["hard_violations"]:
        print(f"  \u2717 {v['message']}")


def main() -> None:
    catalog = load_catalog()

    print("SCENARIO: small Indian apartment bathroom, tight budget, eco preference")
    rule()
    created = services.create_design({
        "room": {"width_mm": 1800, "depth_mm": 2100, "wet_walls": ["N"]},
        "budget": {"max_inr": 80_000},
        "hard_required": ["toilet", "vanity", "faucet"],
        "preferences": {"styles": ["eco"]},
        "constraints_profile": "compact_apt",
    })
    print(f"Room: 1800x2100mm | Budget: {money(80_000)} | Profile: compact_apt | "
          f"Preference: eco")
    print()

    gen = services.generate(created["id"])
    show_result("STEP 1 \u2014 Initial generate", gen)
    print(f"  Soft score: {round(gen['soft_scores']['total'] * 100)}% match "
          f"(sustainability {round(gen['soft_scores']['sustainability'] * 100)}%)")
    print()
    print(f'  "{gen["explanation"]}"'.replace("\n", "\n  "))
    rule()

    spec_dict = store.spec_to_dict(store.get(created["id"])["spec"])

    # Simulated intent extraction for "add a rain shower" \u2014 this is what
    # a correctly-functioning real LLM call would produce; injected here
    # since this sandbox has no network. Everything downstream of this
    # line (merge, re-solve, repair-alternative search, explainer) is
    # the real, tested pipeline \u2014 nothing else is simulated.
    fake_intent_add_shower = lambda s, u: (
        '{"hard_required": ["toilet","vanity","faucet","shower"], '
        '"preferences": {"features": ["rain shower"]}}'
    )
    print('USER (chat): "add a rain shower"')
    turn1 = run_chat_turn(spec_dict, "add a rain shower", catalog, fake_intent_add_shower)
    print()
    show_result("STEP 2 \u2014 After adding rain shower", turn1["generate_result"])
    print()
    print(f'  ASSISTANT: "{turn1["explanation"]}"'.replace("\n", "\n  "))
    print()
    print("  Repair alternatives (each actually re-solved, not just suggested):")
    for alt in turn1["alternatives"]:
        mark = "\u2713 would be feasible" if alt["would_be_feasible"] else "\u2717 still infeasible"
        print(f"    - {alt['description']} \u2014 {mark}")
    rule()

    repair_delta = next(a["delta"] for a in turn1["alternatives"] if a["would_be_feasible"])
    import json as _json
    fake_intent_repair = lambda s, u, _d=repair_delta: _json.dumps(_d)
    print('USER (chat): "never mind, drop the shower"')
    turn2 = run_chat_turn(turn1["spec"], "never mind, drop the shower", catalog, fake_intent_repair)
    print()
    show_result("STEP 3 \u2014 After applying the repair", turn2["generate_result"])
    print()
    print(f'  ASSISTANT: "{turn2["explanation"]}"'.replace("\n", "\n  "))
    rule()
    print("Demo complete. Every number above came from an actual run of this script.")


if __name__ == "__main__":
    main()
