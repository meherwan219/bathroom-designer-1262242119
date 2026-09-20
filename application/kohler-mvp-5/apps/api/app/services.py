"""Design service layer: the actual logic behind the /designs router,
with zero FastAPI dependency so it's directly unit-testable. The
router (app/routers/designs.py) is a thin adapter: it calls these
functions and translates DesignNotFound/DesignConflict into HTTP
status codes.
"""
from __future__ import annotations

from app import store
from app.ai import llm_client, vision_client
from app.ai.floorplan import FloorplanValidationError, extract_floorplan
from app.ai.llm_client import LLMError
from app.ai.modify import build_explanation_facts, explain_deterministic, run_chat_turn
from app.engines.catalog_loader import load_catalog
from app.engines.constraints import check_hard_constraints
from app.engines.domain import PlacedItem
from app.engines.recommend.itemsets import generate_top_itemsets, serialize_itemset

_CATALOG = load_catalog()


class DesignNotFound(Exception):
    pass


class DesignConflict(Exception):
    pass


class AlternativeNotFound(Exception):
    pass


def create_design(payload: dict) -> dict:
    record = store.create(payload)
    return {"id": record["id"], "status": record["status"], "spec": store.spec_to_dict(record["spec"])}


def get_design(design_id: str) -> dict:
    record = store.get(design_id)
    if record is None:
        raise DesignNotFound(design_id)
    return {
        "id": record["id"],
        "status": record["status"],
        "spec": store.spec_to_dict(record["spec"]),
        "last_result": record["last_result"],
    }


def update_spec(design_id: str, payload: dict) -> dict:
    record = store.update_spec(design_id, payload)
    if record is None:
        raise DesignNotFound(design_id)
    return {"id": record["id"], "status": record["status"], "spec": store.spec_to_dict(record["spec"])}


def generate(design_id: str) -> dict:
    """Generates up to 3 ranked itemsets (plan.md's recommendation
    algorithm: candidate pool -> compat prune -> placement/hard-
    constraint filter -> weighted soft score -> top 3 + traces), and
    persists the best one as the design's current result. The other
    itemsets are returned as `recommendation_alternatives` \u2014 an
    addition beyond plan.md's exact response contract, disclosed here:
    it's additive, every field that contract specifies is still
    present and unchanged in shape.
    """
    record = store.get(design_id)
    if record is None:
        raise DesignNotFound(design_id)

    spec = record["spec"]
    itemsets = generate_top_itemsets(spec, _CATALOG, k=3)

    if not itemsets:
        empty = {"feasible": False, "items": [], "layout_ir": {},
                 "totals": {"price_inr": 0, "budget_inr": spec.budget.max_inr},
                 "hard_violations": [{"code": "no_candidates", "message": "No catalog items match the required categories."}]}
        store.set_result(design_id, empty, "failed")
        return {
            "spec": store.spec_to_dict(spec), "layout_ir": {}, "items": [],
            "totals": empty["totals"], "hard_violations": empty["hard_violations"],
            "soft_scores": None, "explanation": None, "recommendation_alternatives": [],
        }

    serialized = [serialize_itemset(it) for it in itemsets]
    for rank, it in enumerate(serialized):
        it["rank"] = rank
    best, alternatives = serialized[0], serialized[1:]

    status = "feasible" if best["feasible"] else "failed"
    store.set_result(design_id, best, status)

    facts = build_explanation_facts(store.spec_to_dict(spec), best)
    explanation = explain_deterministic(facts)

    return {
        "spec": store.spec_to_dict(spec),
        "layout_ir": best["layout_ir"],
        "items": best["items"],
        "totals": best["totals"],
        "hard_violations": best["hard_violations"],
        "soft_scores": best["score"],
        "explanation": explanation,
        "recommendation_alternatives": alternatives,
    }


def select_alternative(design_id: str, rank: int) -> dict:
    """Re-solves the same spec (itemset generation is deterministic
    given the same spec+catalog) and promotes the itemset at `rank`
    (0 = best, matching the order `generate` returned) to be the
    design's current result. This is what makes 'switch to option 2'
    in the UI actually persist \u2014 a later chat edit continues from the
    selected alternative, not silently reverts to the original best pick.
    """
    record = store.get(design_id)
    if record is None:
        raise DesignNotFound(design_id)

    spec = record["spec"]
    itemsets = generate_top_itemsets(spec, _CATALOG, k=3)
    serialized = [serialize_itemset(it) for it in itemsets]
    if rank < 0 or rank >= len(serialized):
        raise AlternativeNotFound(f"rank {rank} out of range (0..{len(serialized) - 1})")

    for i, it in enumerate(serialized):
        it["rank"] = i
    chosen = serialized[rank]
    others = [it for it in serialized if it["rank"] != rank]

    status = "feasible" if chosen["feasible"] else "failed"
    store.set_result(design_id, chosen, status)

    facts = build_explanation_facts(store.spec_to_dict(spec), chosen)
    explanation = explain_deterministic(facts)

    return {
        "spec": store.spec_to_dict(spec),
        "layout_ir": chosen["layout_ir"],
        "items": chosen["items"],
        "totals": chosen["totals"],
        "hard_violations": chosen["hard_violations"],
        "soft_scores": chosen["score"],
        "explanation": explanation,
        "recommendation_alternatives": others,
    }


def validate(design_id: str) -> dict:
    record = store.get(design_id)
    if record is None:
        raise DesignNotFound(design_id)
    if record["last_result"] is None:
        raise DesignConflict(f"{design_id} has not been generated yet")

    spec = record["spec"]
    catalog_by_sku = {p.sku: p for p in _CATALOG}
    items = [
        PlacedItem(role=i["role"], product=catalog_by_sku[i["sku"]])
        for i in record["last_result"]["items"]
        if i["sku"] in catalog_by_sku
    ]
    violations = check_hard_constraints(spec, items)
    return {"hard_violations": [{"code": v.code, "message": v.message} for v in violations]}


def chat_modify(design_id: str, message: str) -> dict:
    """Runs one conversational-modify turn: extract intent -> merge ->
    re-solve -> explain (+ repair alternatives if infeasible), then
    persists the resulting spec/result on the design.

    Uses the real llm_client.complete for both the intent and explainer
    calls. Without a configured LLM_API_KEY (the default in this repo),
    llm_client raises LLMError immediately and app.ai.modify's fail-
    closed guardrail takes over: no delta is applied, and the
    deterministic explainer template is used instead of crashing.
    """
    record = store.get(design_id)
    if record is None:
        raise DesignNotFound(design_id)

    spec_dict = store.spec_to_dict(record["spec"])
    turn = run_chat_turn(
        spec_dict, message, _CATALOG,
        intent_llm_call=llm_client.complete,
        explainer_llm_call=llm_client.complete,
    )

    store.replace_spec(design_id, turn["spec"])
    status = "feasible" if turn["generate_result"]["feasible"] else "failed"
    store.set_result(design_id, turn["generate_result"], status)

    return {
        "reply": turn["explanation"],
        "extracted_delta": turn["extracted_delta"],
        "spec": turn["spec"],
        "layout_ir": turn["generate_result"]["layout_ir"],
        "items": turn["generate_result"]["items"],
        "totals": turn["generate_result"]["totals"],
        "hard_violations": turn["generate_result"]["hard_violations"],
        "alternatives": turn["alternatives"],
    }


def floorplan_proposal(image_base64: str) -> dict:
    """Returns a DRAFT floor-plan proposal only \u2014 width/depth/doors/
    confidence, extracted from an uploaded image. This function never
    touches app.store and never creates or modifies a design. A
    proposal becomes real only if the user submits it back through
    update_spec, the same validated path a typed-in number takes.
    That's not a policy this function has to remember to follow \u2014
    it's structural: there is no design_id parameter, no store import
    used for writing, nothing here CAN persist a proposal even if
    the guardrail in app.ai.floorplan were somehow bypassed.

    Without a configured LLM_API_KEY (this repo's default), the vision
    call raises immediately and this returns {"proposal": None,
    "error": "..."} \u2014 the same fail-closed shape as any other
    unreadable image, not a crash.
    """
    try:
        proposal = extract_floorplan(image_base64, vision_client.complete_with_image)
        return {"proposal": proposal, "error": None}
    except (FloorplanValidationError, LLMError) as e:
        return {"proposal": None, "error": str(e)}
