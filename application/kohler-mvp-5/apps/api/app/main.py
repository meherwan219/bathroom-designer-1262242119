"""FastAPI app entrypoint.

Boots the app, serves /api/v1/health, and serves the OpenAPI schema at
/api/v1/openapi.json. Routers wire in create/generate/chat/vision;
real logic lives in app/services.py and app/ai/*.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import catalog, chat, designs, layout, vision

API_PREFIX = "/api/v1"

app = FastAPI(
    title="KOHLER AI Bathroom Designer API",
    version="0.1.0",
    description=(
        "Deterministic constraint/recommendation/layout engines "
        "with LLM-assisted intent extraction. See project README "
        "for the Design Compiler architecture."
    ),
    openapi_url=f"{API_PREFIX}/openapi.json",
    docs_url=f"{API_PREFIX}/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router, prefix=API_PREFIX)
app.include_router(designs.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(layout.router, prefix=API_PREFIX)
app.include_router(vision.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["health"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get(f"{API_PREFIX}/config", tags=["health"])
def config() -> dict:
    """Feature flags the frontend needs to decide what to show \u2014
    e.g. whether to render the 3D toggle at all. Per plan.md's
    ENABLE_3D feature flag; enable_vision gates the floor-plan upload
    UI the same way."""
    return {"enable_3d": settings.enable_3d, "enable_vision": settings.enable_vision}
