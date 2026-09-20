"""Smoke test for Phase 0: app imports and health check responds."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_served():
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
