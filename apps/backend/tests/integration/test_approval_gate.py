import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import DatabaseConnection, OptimizationExperiment, User


@pytest_asyncio.fixture
async def approval_gate_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_human_approval_gate_strictly_enforced(approval_gate_db):
    user_dba_id = uuid.uuid4()
    user_viewer_id = uuid.uuid4()
    conn_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with approval_gate_db() as db:
        dba_user = User(
            id=user_dba_id,
            email="dba@example.com",
            hashed_password="pw",
            role="dba",
            is_active=True,
        )
        viewer_user = User(
            id=user_viewer_id,
            email="viewer@example.com",
            hashed_password="pw",
            role="viewer",
            is_active=True,
        )
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_dba_id,
            name="Production Gate DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="gatedb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            id=exp_id,
            connection_id=conn_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_gate_test ON orders(id)",
            baseline_p95=120.0,
            candidate_p95=35.0,
            policy_verdict="VERIFIED",
            success=True,
            status="SIMULATED",
        )
        db.add_all([dba_user, viewer_user, conn, exp])
        await db.commit()

    async def override_db():
        async with approval_gate_db() as session:
            yield session

    app.dependency_overrides[deps.get_db_session] = override_db

    try:
        # 1. Negative Test: Deploy without approval -> must return 403
        app.dependency_overrides[deps.get_current_user] = lambda: dba_user
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unapproved_deploy = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert unapproved_deploy.status_code == 403
            assert "human approval required" in unapproved_deploy.json()["error"]["message"].lower()

            # 2. Negative Test: Viewer attempts approval -> must return 403
            app.dependency_overrides[deps.get_current_user] = lambda: viewer_user
            viewer_approve = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Viewer trying to approve"},
            )
            assert viewer_approve.status_code == 403
            assert "not authorized" in viewer_approve.json()["error"]["message"].lower()

            # 3. Positive Test: DBA approves recommendation -> must return 200
            app.dependency_overrides[deps.get_current_user] = lambda: dba_user
            dba_approve = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Approved by Lead DBA after review"},
            )
            assert dba_approve.status_code == 200
            assert dba_approve.json()["action"] == "APPROVE"

            # 4. Positive Test: Deploy now succeeds -> must return 201
            deploy_res = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert deploy_res.status_code == 201
            assert deploy_res.json()["status"] == "RUNNING"
    finally:
        app.dependency_overrides.clear()
