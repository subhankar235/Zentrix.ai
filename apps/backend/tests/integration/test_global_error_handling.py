import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InsufficientTelemetryError,
    PolicyViolationError,
    ResourceNotFoundError,
    ShadowDBProvisioningError,
    UnconfiguredPricingTierError,
    format_error_response,
)
from app.db.base import Base
from app.main import app
from app.models import DatabaseConnection, User


@pytest_asyncio.fixture
async def error_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_domain_exception_instantiation_and_formatting():
    err1 = InsufficientTelemetryError("Only 3 points available", details={"count": 3})
    assert err1.status_code == 422
    assert err1.code == "INSUFFICIENT_TELEMETRY"

    err2 = ShadowDBProvisioningError("Docker daemon socket unreachable")
    assert err2.status_code == 503
    assert err2.code == "SHADOW_DB_PROVISION_FAILED"

    err3 = UnconfiguredPricingTierError("Tier azure_standard unknown")
    assert err3.status_code == 422
    assert err3.code == "COST_MODEL_NOT_CONFIGURED"

    envelope = format_error_response(err1.code, err1.message, err1.status_code, err1.details)
    assert "error" in envelope
    assert envelope["error"]["code"] == "INSUFFICIENT_TELEMETRY"
    assert envelope["error"]["details"]["count"] == 3


@pytest.mark.asyncio
async def test_401_unauthenticated_error_standard_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Accessing protected route without Authorization header
        res = await client.get("/api/v1/connections")
        assert res.status_code == 401
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHENTICATED"
        assert data["error"]["status_code"] == 401


@pytest.mark.asyncio
async def test_404_not_found_error_standard_format(error_test_db):
    user_id = uuid.uuid4()
    non_existent_id = uuid.uuid4()

    async def override_db():
        async with error_test_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="err_test@example.com", hashed_password="pw", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(f"/api/v1/connections/{non_existent_id}")
            assert res.status_code == 404
            data = res.json()
            assert "error" in data
            assert data["error"]["code"] == "NOT_FOUND"
            assert data["error"]["status_code"] == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_422_validation_error_standard_format(error_test_db):
    user_id = uuid.uuid4()

    async def override_db():
        async with error_test_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="err_test@example.com", hashed_password="pw", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # POST connection with invalid port (string instead of int, missing required fields)
            res = await client.post(
                "/api/v1/connections",
                json={"name": "Bad Conn", "port": "not_an_int"},
            )
            assert res.status_code == 422
            data = res.json()
            assert "error" in data
            assert data["error"]["code"] == "VALIDATION_ERROR"
            assert "validation_errors" in data["error"]["details"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_403_forbidden_rbac_standard_format(error_test_db):
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async def override_db():
        async with error_test_db() as session:
            yield session

    # User with unauthorized role 'viewer'
    async def override_user():
        return User(id=user_id, email="viewer@example.com", hashed_password="pw", role="viewer", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Approved by unauthorized viewer"},
            )
            assert res.status_code == 403
            data = res.json()
            assert "error" in data
            assert data["error"]["code"] == "FORBIDDEN"
            assert "not authorized" in data["error"]["message"].lower()
    finally:
        app.dependency_overrides.clear()
