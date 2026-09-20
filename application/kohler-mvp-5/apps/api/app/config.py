"""Runtime configuration, read from environment variables.

Stdlib-only (os.environ), not pydantic-settings: this repo's actual
constraint is that several environments running these files (this
sandbox, CI without full deps installed) don't have every package in
requirements.txt available, and nothing here needs more than "read a
string/bool from the environment with a default." docker-compose.yml
already populates the environment via env_file, so no .env parser is
needed at runtime either.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://kohler:kohler_dev@localhost:5432/kohler"
    )
    llm_provider: str = os.environ.get("LLM_PROVIDER", "anthropic")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "changeme")
    llm_model: str = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    enable_3d: bool = _env_bool("ENABLE_3D", False)
    enable_vision: bool = _env_bool("ENABLE_VISION", False)


settings = Settings()
