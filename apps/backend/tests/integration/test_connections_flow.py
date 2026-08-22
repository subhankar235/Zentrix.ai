import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app
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
async def test_connection_crud_lifecycle_flow(conn_flow_db):
    user_id = uuid.uuid4()

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

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
            assert create_res.status_code == 201
            created = create_res.json()
            conn_id = created["id"]
            assert created["name"] == "Production Analytics DB"
            assert "encrypted_connection_string" not in created  # Sensitive info not exposed

            # 2. List connections
            list_res = await client.get("/api/v1/connections")
            assert list_res.status_code == 200
            connections_list = list_res.json()
            assert len(connections_list) >= 1
            assert any(c["id"] == conn_id for c in connections_list)

            # 3. Get single connection
            get_res = await client.get(f"/api/v1/connections/{conn_id}")
            assert get_res.status_code == 200
            assert get_res.json()["database_name"] == "analytics_prod"

            # 4. Update connection
            patch_res = await client.patch(
                f"/api/v1/connections/{conn_id}",
                json={"name": "Updated Analytics DB"},
            )
            assert patch_res.status_code == 200
            assert patch_res.json()["name"] == "Updated Analytics DB"

            # 5. Delete connection
            del_res = await client.delete(f"/api/v1/connections/{conn_id}")
            assert del_res.status_code == 204

            # 6. Confirm 404 after deletion
            get_del_res = await client.get(f"/api/v1/connections/{conn_id}")
            assert get_del_res.status_code == 404
    finally:
        app.dependency_overrides.clear()
