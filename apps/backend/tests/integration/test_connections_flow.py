import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app as fastapi_app
from app.models.user import User


@pytest_asyncio.fixture
async def conn_flow_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_connection_crud_lifecycle_flow(conn_flow_db, monkeypatch):
    user_id = uuid.uuid4()

    import sys
    import app.services.connection_service
    from app.schemas.connection import ConnectionTestResponse

    async def mock_verify(raw_dsn):
        return ConnectionTestResponse(
            success=True,
            postgres_version="PostgreSQL 16.3",
            latency_ms=1.5,
            permissions={"pg_stat_statements": True, "read_only_role": True},
        )

    monkeypatch.setattr(sys.modules["app.services.connection_service"], "verify_raw_dsn", mock_verify)

    async with conn_flow_db() as db:
        user = User(
            id=user_id,
            email="conn_owner@example.com",
            hashed_password="pw",
            is_active=True,
        )
        db.add(user)
        await db.commit()

    async def override_db():
        async with conn_flow_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="conn_owner@example.com", hashed_password="pw", is_active=True)

    fastapi_app.dependency_overrides[deps.get_db_session] = override_db
    fastapi_app.dependency_overrides[deps.get_current_user] = override_user
    fastapi_app.dependency_overrides[deps.get_connection_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
            # 1. Create connection
            create_payload = {
                "name": "Production Analytics DB",
                "host": "localhost",
                "port": 5432,
                "database_name": "analytics_prod",
                "username": "zentrix_agent",
                "password": "agent_password",
                "ssl_mode": "prefer",
            }
            create_res = await client.post("/api/v1/connections", json=create_payload)
            assert create_res.status_code == 201, f"Create failed: {create_res.status_code} {create_res.text}"
            created = create_res.json()
            conn_id = created["id"]
            assert created["name"] == "Production Analytics DB"
            assert "encrypted_connection_string" not in created  # Sensitive info not exposed

            # 2. List connections
            list_res = await client.get("/api/v1/connections")
            assert list_res.status_code == 200, f"List failed: {list_res.status_code} {list_res.text}"
            connections_list = list_res.json()
            assert len(connections_list) >= 1
            assert any(c["id"] == conn_id for c in connections_list)

            # 3. Get single connection
            get_res = await client.get(f"/api/v1/connections/{conn_id}")
            assert get_res.status_code == 200, f"Get failed: {get_res.status_code} {get_res.text}"
            assert get_res.json()["database_name"] == "analytics_prod"

            # 4. Update connection
            patch_res = await client.patch(
                f"/api/v1/connections/{conn_id}",
                json={"name": "Updated Analytics DB"},
            )
            assert patch_res.status_code == 200, f"Patch failed: {patch_res.status_code} {patch_res.text}"
            assert patch_res.json()["name"] == "Updated Analytics DB"

            # 5. Delete connection
            del_res = await client.delete(f"/api/v1/connections/{conn_id}")
            assert del_res.status_code == 204, f"Delete failed: {del_res.status_code} {del_res.text}"

            # 6. Confirm 404 after deletion
            get_del_res = await client.get(f"/api/v1/connections/{conn_id}")
            assert get_del_res.status_code == 404, f"Get after delete failed: {get_del_res.status_code} {get_del_res.text}"
    finally:
        fastapi_app.dependency_overrides.clear()
