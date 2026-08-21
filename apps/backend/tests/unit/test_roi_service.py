import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import DatabaseConnection, OptimizationExperiment, RoiRecord, User
from app.services.roi_service import (
    compute_deterministic_roi,
    get_pricing_tier,
    roi_service,
)


def test_get_pricing_tier_configured_and_unconfigured():
    # 1. Standard / AWS RDS / Neon / GCP configured tiers
    aws = get_pricing_tier("aws_rds_standard")
    assert aws["is_configured"] is True
    assert aws["cpu_cost_per_hour_usd"] > 0
    assert aws["io_cost_per_million_reads_usd"] > 0

    neon = get_pricing_tier("neon_serverless")
    assert neon["is_configured"] is True

    # 2. Unknown pricing tier -> returns not configured
    unknown = get_pricing_tier("non_existent_provider")
    assert unknown["is_configured"] is False
    assert unknown["cpu_cost_per_hour_usd"] == 0.0


def test_deterministic_roi_calculation_math():
    # Input parameters
    baseline_cpu = 0.50  # sec/query
    cand_cpu = 0.20  # sec/query -> delta = 0.30 sec/query
    baseline_io = 2000.0  # blks/query
    cand_io = 500.0  # blks/query -> delta = 1500 blks/query
    freq_day = 100_000.0  # 100k queries/day

    # Standard rates: CPU=$0.04/hr, IO=$0.20/1M, Storage=$0.115/GB-mo
    # Monthly calls = 100,000 * 30.4167 = 3,041,670 calls
    # Delta CPU sec total = 3,041,670 * 0.30 = 912,501 sec
    # Compute savings = (912,501 / 3600) * 0.04 = 253.4725 * 0.04 = $10.14
    # IO delta total = 3,041,670 * 1500 = 4,562,505,000 blks
    # IO savings = (4,562,505,000 / 1,000,000) * 0.20 = 4,562.505 * 0.20 = $912.50
    # Total ~ $922.64

    res = compute_deterministic_roi(
        baseline_cpu_seconds=baseline_cpu,
        candidate_cpu_seconds=cand_cpu,
        baseline_io_reads=baseline_io,
        candidate_io_reads=cand_io,
        frequency_per_day=freq_day,
        pricing_tier="standard",
        index_storage_mb=10.0,
    )

    assert res["is_cost_model_configured"] is True
    assert res["compute_savings_usd"] == 10.14
    assert res["io_savings_usd"] == 912.50
    assert res["estimated_monthly_savings_usd"] > 900.0
    assert "formula" in res["calculation_details"]


def test_unconfigured_pricing_tier_returns_unconfigured_status():
    res = compute_deterministic_roi(
        baseline_cpu_seconds=0.5,
        candidate_cpu_seconds=0.2,
        baseline_io_reads=1000,
        candidate_io_reads=200,
        frequency_per_day=50_000,
        pricing_tier="unsupported_tier_xyz",
    )
    assert res["is_cost_model_configured"] is False
    assert res["estimated_monthly_savings_usd"] == 0.0
    assert res["calculation_details"]["status"] == "COST_MODEL_NOT_CONFIGURED"


@pytest_asyncio.fixture
async def roi_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_roi_service_calculate_and_save(roi_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async with roi_db() as db:
        user = User(id=user_id, email="roi_test@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="ROI DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="roidb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            connection_id=conn_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_roi ON orders(id)",
            baseline_cpu=0.60,
            candidate_cpu=0.20,
            baseline_io=3000.0,
            candidate_io=500.0,
            baseline_p95=120.0,
            candidate_p95=40.0,
            policy_verdict="VERIFIED",
            success=True,
            status="DEPLOYED",
        )
        db.add_all([user, conn, exp])
        await db.commit()

        # Calculate and save ROI
        record = await roi_service.calculate_and_save_experiment_roi(
            experiment_id=exp.id,
            db=db,
            pricing_tier="aws_rds_standard",
            frequency_per_day=50_000.0,
        )

        assert record.id is not None
        assert record.estimated_monthly_savings_usd > 0.0
        assert record.compute_savings_usd > 0.0
        assert record.io_savings_usd > 0.0
        assert record.assumed_pricing_tier == "aws_rds_standard"

        # Summary retrieval
        summary = await roi_service.get_connection_roi_summary(conn_id, db)
        assert summary.connection_id == conn_id
        assert summary.total_monthly_savings_usd == record.estimated_monthly_savings_usd
        assert summary.optimizations_count == 1
