"""Optional vision-assisted floor-plan endpoint. Always human-confirmed.

Returns a DRAFT proposal only \u2014 see app.services.floorplan_proposal's
docstring for why this can't write to any design's spec even in
principle, not just by convention.
"""
from fastapi import APIRouter

from app import services

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/floorplan")
def floorplan_from_image(payload: dict):
    """payload: {"image_base64": str}. Returns
    {"proposal": {...} | null, "error": str | null}. The frontend must
    show this as an editable draft and let the user confirm/adjust
    before calling PATCH /designs/{id}/spec \u2014 this endpoint never
    calls that itself."""
    image_base64 = payload.get("image_base64", "")
    return services.floorplan_proposal(image_base64)
