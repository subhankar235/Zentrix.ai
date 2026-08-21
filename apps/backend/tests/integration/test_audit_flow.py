import json
import logging
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.core.logging import (
    StructuredJSONFormatter,
    clear_correlation_context,
    get_correlation_context,
    log_agent_execution,
    set_correlation_context,
)
from app.db.base import Base
from app.main import app
from app.models import (
    Approval,
    AuditLog,
    CanaryRun,
    DatabaseConnection,
    OptimizationExperiment,
    RoiRecord,
    User,
)
from app.services.audit_service import audit_service
from app.services.roi_service import roi_service
from app.services.simulation_service import simulation_service
from app.workers.canary_monitor import execute_commit, execute_rollback


@pytest_asyncio.fixture
async def audit_test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_logging_correlation_context_and_json_formatter():
    clear_correlation_context()
    set_correlation_context(
        request_id="req-999",
        agent_id="SupervisorAgent",
        experiment_id="exp-111",
        connection_id="conn-222",
    )

    ctx = get_correlation_context()
    assert ctx["request_id"] == "req-999"
    assert ctx["agent_id"] == "SupervisorAgent"

    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="zentrix.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test correlation logging",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["request_id"] == "req-999"
    assert parsed["agent_id"] == "SupervisorAgent"
    assert parsed["experiment_id"] == "exp-111"
    assert parsed["connection_id"] == "conn-222"
    assert parsed["message"] == "Test correlation logging"

    clear_correlation_context()
    assert get_correlation_context() == {}


@pytest.mark.asyncio
async def test_full_lifecycle_audit_trail_completeness(audit_test_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async with audit_test_db() as db:
        user = User(
            id=user_id,
            email="dba_audit@example.com",
            hashed_password="pw",
            role="dba",
            is_active=True,
        )
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="Audit Monitored DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="auditdb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        # 1. Step: Simulation Execution -> creates SIMULATION_EXECUTED audit
        candidate_data = {
            "strategy": "CREATE_INDEX",
            "candidate_sql": "CREATE INDEX CONCURRENTLY idx_audit_test ON orders(created_at);",
            "table_name": "orders",
            "baseline_p95": 100.0,
            "candidate_p95": 30.0,
        }
        exp = await simulation_service.run_simulation(conn_id, candidate_data, db)
        assert exp.id is not None

        # 2. Step: Human Approval -> creates RECOMMENDATION_APPROVED audit
        approval = await simulation_service.approve_recommendation(
            exp.id, user, "Verified by senior DBA", db
        )
        assert approval.action == "APPROVE"

        # 3. Step: Canary Deployment -> creates CANARY_START audit
        canary = await simulation_service.deploy_canary(exp.id, user.id, db)
        assert canary.status == "RUNNING"

        # 4. Step: Canary Commit -> creates CANARY_COMMIT audit
        await execute_commit(canary, exp, db)

        # 5. Step: ROI Calculation -> creates ROI_CALCULATED audit
        roi_rec = await roi_service.calculate_and_save_experiment_roi(
            exp.id, db, pricing_tier="aws_rds_standard", frequency_per_day=50_000.0
        )
        assert roi_rec.estimated_monthly_savings_usd > 0

        # Query full audit trail
        logs_resp = await audit_service.list_audit_logs(db, connection_id=conn_id)
        assert logs_resp.total >= 4

        actions = [item.action_type for item in logs_resp.items]
        assert "SIMULATION_EXECUTED" in actions
        assert "RECOMMENDATION_APPROVED" in actions
        assert "CANARY_START" in actions
        assert "CANARY_COMMIT" in actions
        assert "ROI_CALCULATED" in actions


@pytest.mark.asyncio
async def test_audit_api_endpoints(audit_test_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async with audit_test_db() as db:
        user = User(
            id=user_id,
            email="auditor@example.com",
            hashed_password="pw",
            role="admin",
            is_active=True,
        )
        conn = DatabaseConnection(
            id=conn_id,
            user_id=user_id,
            name="Audit API DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="auditapidb",
            username="postgres",
            is_active=True,
        )
        audit1 = AuditLog(
            user_id=user_id,
            connection_id=conn_id,
            action_type="USER_LOGIN",
            target_entity="user",
            target_id=str(user_id),
            details={"ip": "127.0.0.1"},
            timestamp=datetime.now(timezone.utc),
        )
        audit2 = AuditLog(
            user_id=user_id,
            connection_id=conn_id,
            action_type="CANARY_ROLLBACK",
            target_entity="canary_run",
            target_id="canary-1",
            details={"reason": "p95 threshold breached"},
            timestamp=datetime.now(timezone.utc),
        )
        db.add_all([user, conn, audit1, audit2])
        await db.commit()

    async def override_db():
        async with audit_test_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="auditor@example.com", hashed_password="pw", role="admin", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. GET /api/v1/audit/logs
            res1 = await client.get("/api/v1/audit/logs")
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["total"] >= 2
            assert len(data1["items"]) >= 2

            # 2. GET /api/v1/connections/{id}/audit-logs
            res2 = await client.get(f"/api/v1/connections/{conn_id}/audit-logs")
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["total"] >= 2

            # 3. GET /api/v1/audit/canary-runs
            res3 = await client.get(f"/api/v1/audit/canary-runs?connection_id={conn_id}")
            assert res3.status_code == 200
            assert isinstance(res3.json(), list)
    finally:
        app.dependency_overrides.clear()
