"""Design lifecycle endpoints: create, load, update spec, generate,
validate. All real logic lives in app/services.py (framework-free);
this router only translates payloads/exceptions to HTTP.
"""
from fastapi import APIRouter, HTTPException

from app import services

router = APIRouter(prefix="/designs", tags=["designs"])


@router.post("")
def create_design(payload: dict):
    """Create a design from an intake-form payload. See
    app.store.spec_from_dict for the expected shape."""
    return services.create_design(payload)


@router.get("/{design_id}")
def get_design(design_id: str):
    try:
        return services.get_design(design_id)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")


@router.patch("/{design_id}/spec")
def update_spec(design_id: str, payload: dict):
    try:
        return services.update_spec(design_id, payload)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")


@router.post("/{design_id}/generate")
def generate_design(design_id: str):
    try:
        return services.generate(design_id)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")


@router.post("/{design_id}/select/{rank}")
def select_alternative(design_id: str, rank: int):
    """Promotes the itemset at `rank` (0 = best, as returned by
    generate/its recommendation_alternatives) to the design's current
    result. Not in plan.md's original endpoint table \u2014 an addition to
    make the top-3 alternatives actually selectable, not just visible.
    """
    try:
        return services.select_alternative(design_id, rank)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")
    except services.AlternativeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{design_id}/validate")
def validate_design(design_id: str):
    try:
        return services.validate(design_id)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")
    except services.DesignConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
