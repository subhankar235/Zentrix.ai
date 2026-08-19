"""
Integration tests for Step 12: Connection Onboarding Service and Routes.
Verifies registration, reachability testing, permission checks, and telemetry summary.
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.main import app
from app.models.user import User
from app.schemas.connection import ConnectionCreate
from app.services.connection_service import connection_service, verify_raw_dsn



@pytest.mark.asyncio
async def test_test_raw_dsn_against_live_database():
    """Verify verify_raw_dsn connects and checks permissions against live Neon PostgreSQL."""
    settings = get_settings()
    res = await verify_raw_dsn(settings.APP_DATABASE_URL)

    assert res.success is True
    assert res.postgres_version is not None
    assert "PostgreSQL" in res.postgres_version
    assert res.latency_ms is not None
    assert res.latency_ms > 0
    assert "pg_stat_activity" in res.permissions
    assert "pg_stat_user_tables" in res.permissions


@pytest.mark.asyncio
async def test_connection_service_lifecycle():
    """Verify ConnectionService full lifecycle against real database."""
    settings = get_settings()

    async with async_session_factory() as session:
        # 1. Create test user
        user = User(
            id=uuid.uuid4(),
            email=f"service_test_{uuid.uuid4().hex[:8]}@zentrix.ai",
            hashed_password="hashed_pw_test",
            role="dba",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 2. Register new connection via service
        conn_in = ConnectionCreate(
            name="Neon Integration Test DB",
            host="ep-dawn-pond-axb4kmt3-pooler.c-4.us-east-2.aws.neon.tech",
            port=5432,
            database_name="neondb",
            username="neondb_owner",
            ssl_mode="require",
            connection_string=settings.APP_DATABASE_URL,
        )
        conn_record = await connection_service.create_connection(
            user_id=user.id,
            conn_in=conn_in,
            db=session,
        )
        assert conn_record.id is not None
        assert conn_record.encrypted_connection_string != settings.APP_DATABASE_URL
        assert conn_record.permission_status is not None

        # 3. Test connection via service
        test_res = await connection_service.test_connection(
            connection_id=conn_record.id,
            user_id=user.id,
            is_superuser=False,
            db=session,
        )
        assert test_res.success is True
        assert test_res.postgres_version is not None
        assert "PostgreSQL" in test_res.postgres_version

        # 4. List connections
        connections = await connection_service.list_connections(
            user_id=user.id,
            is_superuser=False,
            db=session,
        )
        assert len(connections) >= 1
        assert any(c.id == conn_record.id for c in connections)

        # 5. Get telemetry summary
        summary = await connection_service.get_telemetry_summary(
            connection_id=conn_record.id,
            user_id=user.id,
            is_superuser=False,
            db=session,
        )
        assert summary is not None
        assert summary.connection_id == conn_record.id

        # 6. Delete connection
        deleted = await connection_service.delete_connection(
            connection_id=conn_record.id,
            user_id=user.id,
            is_superuser=False,
            db=session,
        )
        assert deleted is True

        # Cleanup user
        await session.delete(user)
        await session.commit()


@pytest.mark.asyncio
async def test_api_connections_endpoints():
    """Verify HTTP API endpoints for POST /connections and POST /connections/{id}/test."""
    settings = get_settings()

    async with async_session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"api_test_{uuid.uuid4().hex[:8]}@zentrix.ai",
            hashed_password="hashed_pw_test",
            role="admin",
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register connection via API
        payload = {
            "name": "API Neon Test DB",
            "host": "ep-dawn-pond-axb4kmt3-pooler.c-4.us-east-2.aws.neon.tech",
            "port": 5432,
            "database_name": "neondb",
            "username": "neondb_owner",
            "ssl_mode": "require",
            "provider": "neon",
            "connection_string": settings.APP_DATABASE_URL,
        }
        res_create = await client.post("/api/v1/connections", json=payload, headers=headers)
        assert res_create.status_code == 201
        conn_data = res_create.json()
        conn_id = conn_data["id"]

        # 2. Test connection via API
        res_test = await client.post(f"/api/v1/connections/{conn_id}/test", headers=headers)
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data["success"] is True
        assert test_data["postgres_version"] is not None

        # 3. Get connection details
        res_get = await client.get(f"/api/v1/connections/{conn_id}", headers=headers)
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "API Neon Test DB"

        # 4. Get telemetry summary
        res_telem = await client.get(f"/api/v1/connections/{conn_id}/telemetry", headers=headers)
        assert res_telem.status_code == 200
        assert res_telem.json()["connection_id"] == conn_id

        # 5. Delete connection
        res_del = await client.delete(f"/api/v1/connections/{conn_id}", headers=headers)
        assert res_del.status_code == 204

    # Cleanup user
    async with async_session_factory() as session:
        user_to_delete = await session.get(User, user.id)
        if user_to_delete:
            await session.delete(user_to_delete)
            await session.commit()


