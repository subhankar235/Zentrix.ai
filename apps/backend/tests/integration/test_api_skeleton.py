"""
Integration tests for Step 10: Core API Skeleton and Route Registration.
Verifies FastAPI app startup, OpenAPI schema generation, route wiring, and 401 guard behavior.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.core.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify GET / returns online service metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Zentrix.ai"
        assert data["status"] == "online"


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Verify GET /health checks database reachability."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_openapi_schema_contains_all_routes():
    """Verify OpenAPI schema renders all PRD endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        paths = schema.get("paths", {})

        expected_paths = [
            "/api/v1/auth/signup",
            "/api/v1/auth/login",
            "/api/v1/auth/logout",
            "/api/v1/auth/me",
            "/api/v1/connections",
            "/api/v1/connections/{id}",
            "/api/v1/connections/{id}/test",
            "/api/v1/connections/{id}/telemetry",
            "/api/v1/connections/{id}/diagnoses",
            "/api/v1/diagnoses/{id}",
            "/api/v1/diagnoses/{id}/recommendations",
            "/api/v1/diagnoses/{id}/investigate",
            "/api/v1/experiments",
            "/api/v1/experiments/{id}",
            "/api/v1/recommendations/{id}/simulate",
            "/api/v1/recommendations/{id}/verification",
            "/api/v1/recommendations/{id}/approve",
            "/api/v1/recommendations/{id}/reject",
            "/api/v1/deployments/{id}",
            "/api/v1/experiments/{id}/canary/stream",
            "/api/v1/forecast/{connectionId}",
            "/api/v1/models/performance",
            "/api/v1/forecasts/{id}/stream",
            "/api/v1/roi/{connectionId}",
            "/api/v1/roi/experiments/{experimentId}",
        ]

        for expected in expected_paths:
            assert expected in paths, f"Expected endpoint {expected} missing from OpenAPI paths"


@pytest.mark.asyncio
async def test_unauthenticated_protected_routes_return_401():
    """Verify unauthenticated requests to protected endpoints return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. /api/v1/auth/me
        res_me = await client.get("/api/v1/auth/me")
        assert res_me.status_code == 401
        data = res_me.json()
        assert "error" in data or "detail" in data
        msg = data.get("error", {}).get("message") or data.get("detail", "")
        assert "Authentication required" in msg

        # 2. /api/v1/connections
        res_conn = await client.get("/api/v1/connections")
        if get_settings().DEV_CONNECTIONS_WITHOUT_AUTH:
            assert res_conn.status_code == 200
        else:
            assert res_conn.status_code == 401

        # 3. /api/v1/experiments
        res_exp = await client.get("/api/v1/experiments")
        assert res_exp.status_code == 401
