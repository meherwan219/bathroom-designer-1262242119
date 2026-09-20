"""Conversational modify endpoint: NL delta -> engines -> re-solve.

Real logic lives in app.services.chat_modify; this router only
translates payload/exceptions to HTTP, matching designs.py's pattern.
"""
from fastapi import APIRouter, HTTPException

from app import services

router = APIRouter(prefix="/designs", tags=["chat"])


@router.post("/{design_id}/chat")
def chat_modify(design_id: str, payload: dict):
    """payload: {"message": str}"""
    message = payload.get("message", "")
    try:
        return services.chat_modify(design_id, message)
    except services.DesignNotFound:
        raise HTTPException(status_code=404, detail="design not found")
