import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.graph_forecast import run_forecast_pipeline
from app.api import deps
from app.db.base import Base
from app.main import app
from app.ml.forecasting.train import generate_synthetic_telemetry_series
from app.models import BanditEvent, DatabaseConnection, ForecastRecord, ModelDriftReport, User
from app.services.forecast_service import forecast_service


@pytest_asyncio.fixture
async def forecast_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_forecast_agent_graph_execution():
    conn_id = str(uuid.uuid4())
    # Generate 30 days telemetry with degradation in last 10 days
    telemetry = generate_synthetic_telemetry_series(n_days=30, degradation_start_day=15)

    res = run_forecast_pipeline(
        connection_id=conn_id,
        telemetry_history=telemetry,
        table_name="customers",
    )

    assert "forecast_result" in res
    assert "strategy_decision" in res
    assert res["status"] in {"ACTION_REQUIRED", "MONITORING_NORMAL"}
    assert len(res["forecast_result"]["probability_curve"]) > 0
    assert res["candidate_spec"] is not None
    assert "CREATE INDEX" in res["candidate_spec"]["candidate_sql"] or "ANALYZE" in res["candidate_spec"]["candidate_sql"]


@pytest.mark.asyncio
async def test_forecast_service_generate_and_persist(forecast_test_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async with forecast_test_db() as db:
        user = User(id=user_id, email="fc_user@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="Forecast DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="fcdb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        # Generate forecast
        response = await forecast_service.generate_forecast(conn_id, query_id=None, db=db)

        assert response.connection_id == conn_id
        assert 0.0 <= response.degradation_probability <= 1.0
        assert len(response.curve) > 0
        assert len(response.suggested_strategies) > 0

        # Verify ForecastRecord persisted
        fc_rec = await db.scalar(select(ForecastRecord).where(ForecastRecord.connection_id == conn_id))
        assert fc_rec is not None
        assert fc_rec.degradation_probability == response.degradation_probability


@pytest.mark.asyncio
async def test_forecast_api_routes(forecast_test_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async with forecast_test_db() as db:
        user = User(id=user_id, email="api_fc@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="API Forecast DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="apifcdb",
            username="postgres",
            is_active=True,
        )
        drift = ModelDriftReport(
            model_name="l1_forecasting",
            model_version="v1",
            dataset_drift_score=0.12,
            prediction_drift_score=0.08,
            is_drift_detected=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([user, conn, drift])
        await db.commit()

    async def override_db():
        async with forecast_test_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="api_fc@example.com", hashed_password="pw", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. GET /api/v1/forecast/{connectionId}
            res1 = await client.get(f"/api/v1/forecast/{conn_id}")
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["connection_id"] == str(conn_id)
            assert len(data1["curve"]) > 0

            # 2. GET /api/v1/connections/{connectionId}/forecasts
            res2 = await client.get(f"/api/v1/connections/{conn_id}/forecasts")
            assert res2.status_code == 200
            assert res2.json()["connection_id"] == str(conn_id)

            # 3. GET /api/v1/models/performance
            res3 = await client.get("/api/v1/models/performance")
            assert res3.status_code == 200
            perf = res3.json()
            assert "mae_over_time" in perf
            assert "rmse_over_time" in perf
            assert "calibration_score" in perf
            assert len(perf["drift_reports"]) >= 1

            # 4. SSE Stream endpoint
            stream_res = await client.get(f"/api/v1/forecasts/{conn_id}/stream")
            assert stream_res.status_code == 200
            assert "text/event-stream" in stream_res.headers["content-type"]
    finally:
        app.dependency_overrides.clear()
