import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import DatabaseConnection, OptimizationExperiment, RoiRecord, User


@pytest_asyncio.fixture
async def roi_api_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_roi_api_endpoints_flow(roi_api_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with roi_api_db() as db:
        user = User(id=user_id, email="api_roi@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="API ROI DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="apiroidb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            id=exp_id,
            connection_id=conn_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_api_roi ON orders(id)",
            baseline_cpu=0.50,
            candidate_cpu=0.15,
            baseline_io=2500.0,
            candidate_io=400.0,
            baseline_p95=100.0,
            candidate_p95=35.0,
            policy_verdict="VERIFIED",
            success=True,
            status="DEPLOYED",
        )
        db.add_all([user, conn, exp])
        await db.commit()

    async def override_db():
        async with roi_api_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="api_roi@example.com", hashed_password="pw", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Calculate ROI via POST
            calc_res = await client.post(
                f"/api/v1/roi/experiments/{exp_id}/calculate",
                params={"pricing_tier": "aws_rds_standard", "frequency_per_day": 80000.0},
            )
            assert calc_res.status_code == 200
            calc_data = calc_res.json()
            assert calc_data["experiment_id"] == str(exp_id)
            assert calc_data["estimated_monthly_savings_usd"] > 0
            assert calc_data["compute_savings_usd"] > 0

            # 2. Get specific experiment ROI
            get_res = await client.get(f"/api/v1/roi/experiments/{exp_id}")
            assert get_res.status_code == 200
            assert get_res.json()["id"] == calc_data["id"]

            # 3. Get connection summary
            summary_res = await client.get(f"/api/v1/roi/{conn_id}")
            assert summary_res.status_code == 200
            sum_data = summary_res.json()
            assert sum_data["connection_id"] == str(conn_id)
            assert sum_data["total_monthly_savings_usd"] == calc_data["estimated_monthly_savings_usd"]
            assert sum_data["optimizations_count"] == 1
    finally:
        app.dependency_overrides.clear()
