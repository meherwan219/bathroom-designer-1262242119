"""Reserved for layout-specific routes (per plan.md's router list).

Currently /designs/{id}/generate and /designs/{id}/validate — which
call the layout + validate engines — live in designs.py per the API
contracts table. This file stays as the named slot for anything that
needs a dedicated /layout/* route later (e.g. re-render, IR diff).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/layout", tags=["layout"])
