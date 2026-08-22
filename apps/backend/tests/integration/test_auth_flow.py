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
async def auth_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_signup_login_token_flow(auth_test_db):
    async def override_db():
        async with auth_test_db() as session:
            yield session

    app.dependency_overrides[deps.get_db_session] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register new user
            email = f"user_{uuid.uuid4().hex[:6]}@example.com"
            register_res = await client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "SecurePassword123!", "full_name": "Test User"},
            )
            assert register_res.status_code == 201
            reg_data = register_res.json()
            assert reg_data["email"] == email
            assert "id" in reg_data

            # 2. Login with JSON credentials
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "SecurePassword123!"},
            )
            assert login_res.status_code == 200
            token_data = login_res.json()
            assert "access_token" in token_data
            token = token_data["access_token"]

            # 3. Access protected /auth/me route
            me_res = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_res.status_code == 200
            me_data = me_res.json()
            assert me_data["email"] == email
            assert me_data["is_active"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_login_invalid_password(auth_test_db):
    async def override_db():
        async with auth_test_db() as session:
            yield session

    app.dependency_overrides[deps.get_db_session] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email = "bad_pw@example.com"
            await client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "CorrectPassword123!"},
            )

            # Try login with wrong password
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPassword123!"},
            )
            assert login_res.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_register_duplicate_email(auth_test_db):
    async def override_db():
        async with auth_test_db() as session:
            yield session

    app.dependency_overrides[deps.get_db_session] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            email = "duplicate@example.com"
            res1 = await client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "Password123!"},
            )
            assert res1.status_code == 201

            # Duplicate signup
            res2 = await client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "Password123!"},
            )
            assert res2.status_code == 400
    finally:
        app.dependency_overrides.clear()
