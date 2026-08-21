import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models import Approval, AuditLog, CanaryRun, DatabaseConnection, OptimizationExperiment, User
from app.services.simulation_service import simulation_service
from app.workers.canary_monitor import check_rollback_condition, generate_rollback_sql, monitor_canary_tick


@pytest_asyncio.fixture
async def simulation_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_rollback_condition_detection():
    # 1. Normal metrics - no breach
    baseline = {"p95_ms": 100.0, "write_mean_ms": 10.0}
    healthy_current = {"p95_ms": 65.0, "write_mean_ms": 10.5, "error_rate": 0.0, "lock_wait_seconds": 0.1}
    breached, reason = check_rollback_condition(baseline, healthy_current)
    assert breached is False
    assert reason is None

    # 2. p95 Latency regression > 15%
    regressed_p95 = {"p95_ms": 125.0, "write_mean_ms": 10.0, "error_rate": 0.0}
    breached, reason = check_rollback_condition(baseline, regressed_p95)
    assert breached is True
    assert "p95 latency regressed" in reason

    # 3. High error rate > 1%
    error_current = {"p95_ms": 70.0, "error_rate": 0.05}
    breached, reason = check_rollback_condition(baseline, error_current)
    assert breached is True
    assert "Query error rate reached" in reason

    # 4. Write latency increase > 20%
    write_regressed = {"p95_ms": 60.0, "write_mean_ms": 15.0}  # 50% increase
    breached, reason = check_rollback_condition(baseline, write_regressed)
    assert breached is True
    assert "Write latency increased" in reason


def test_generate_rollback_sql():
    sql = "CREATE INDEX CONCURRENTLY idx_users_email ON users(email);"
    rollback = generate_rollback_sql(sql)
    assert rollback == "DROP INDEX CONCURRENTLY IF EXISTS idx_users_email"

    unique_sql = "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_id ON orders(id)"
    rollback_unique = generate_rollback_sql(unique_sql)
    assert rollback_unique == "DROP INDEX CONCURRENTLY IF EXISTS idx_orders_id"


@pytest.mark.asyncio
async def test_simulation_service_full_workflow(simulation_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with simulation_db() as db:
        user = User(id=user_id, email="sim_user@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Sim DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="simdb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

        # 1. Run simulation
        candidate = {
            "candidate_sql": "CREATE INDEX CONCURRENTLY idx_orders_customer ON orders(customer_id)",
            "strategy": "CREATE_INDEX",
            "table_name": "orders",
            "baseline_p95": 120.0,
            "candidate_p95": 70.0,
            "sample_size": 30,
        }
        exp = await simulation_service.run_simulation(connection_id, candidate, db)
        assert exp.id is not None
        assert exp.status == "SIMULATED"
        assert exp.policy_verdict == "VERIFIED"
        assert exp.success is True

        # Verify ML prediction record persisted
        exp_loaded = await simulation_service.get_experiment(exp.id, db)
        assert len(exp_loaded.predictions) == 1
        assert exp_loaded.predictions[0].model_version == "delta_predictor_v1"

        # 2. Get Verification Report
        verif = await simulation_service.get_verification(exp.id, db)
        assert verif.is_safe_for_canary is True
        assert verif.policy_verdict == "VERIFIED"

        # 3. Attempt deploy without prior human approval -> raises PermissionError
        with pytest.raises(PermissionError, match="Human approval required"):
            await simulation_service.deploy_canary(exp.id, user_id, db)

        # 4. Record human approval
        db.add(Approval(experiment_id=exp.id, user_id=user_id, action="APPROVE", reason="Looks solid"))
        await db.commit()

        # 5. Deploy canary
        canary = await simulation_service.deploy_canary(exp.id, user_id, db)
        assert canary.status == "RUNNING"
        assert canary.canary_sql_applied == candidate["candidate_sql"]

        # Check Audit Log recorded
        audit = await db.scalar(select(AuditLog).where(AuditLog.action_type == "CANARY_START"))
        assert audit is not None
        assert audit.user_id == user_id


@pytest.mark.asyncio
async def test_canary_monitor_rollback_and_commit(simulation_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with simulation_db() as db:
        user = User(id=user_id, email="canary@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Canary DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="candb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            connection_id=connection_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_items_price ON items(price)",
            baseline_p95=100.0,
            candidate_p95=60.0,
            policy_verdict="VERIFIED",
            success=True,
            status="DEPLOYED",
        )
        db.add_all([user, conn, exp])
        await db.flush()

        canary = CanaryRun(
            experiment_id=exp.id,
            connection_id=connection_id,
            status="RUNNING",
            canary_sql_applied=exp.candidate_sql,
            observation_window_minutes=15,
            baseline_metrics={"p95_ms": 100.0, "write_mean_ms": 10.0},
        )
        db.add(canary)
        await db.commit()

        # 1. Monitoring tick with regression triggers automatic rollback
        regressed_metrics = {"p95_ms": 130.0, "write_mean_ms": 10.0, "error_rate": 0.0}
        res = await monitor_canary_tick(canary, db, current_metrics=regressed_metrics)
        assert res["status"] == "ROLLED_BACK"

        # Verify database records updated
        await db.refresh(canary)
        await db.refresh(exp)
        assert canary.status == "ROLLED_BACK"
        assert "p95 latency regressed" in canary.rollback_reason
        assert exp.status == "ROLLED_BACK"
        assert exp.rollback is True

        rollback_audit = await db.scalar(select(AuditLog).where(AuditLog.action_type == "CANARY_ROLLBACK"))
        assert rollback_audit is not None


@pytest.mark.asyncio
async def test_experiments_api_routes(simulation_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with simulation_db() as db:
        user = User(id=user_id, email="api_exp@example.com", hashed_password="pw", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="API Test DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="apidb",
            username="postgres",
            is_active=True,
        )
        db.add_all([user, conn])
        await db.commit()

    async def override_db():
        async with simulation_db() as session:
            yield session

    async def override_user():
        return User(id=user_id, email="api_exp@example.com", hashed_password="pw", role="dba", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Simulate
            sim_res = await client.post(
                f"/api/v1/recommendations/{uuid.uuid4()}/simulate",
                json={
                    "strategy": "CREATE_INDEX",
                    "candidate_sql": "CREATE INDEX CONCURRENTLY idx_users_city ON users(city)",
                    "table_name": "users",
                },
            )
            assert sim_res.status_code == 202
            exp_data = sim_res.json()
            exp_id = exp_data["id"]

            # 2. Get Verification
            verif_res = await client.get(f"/api/v1/recommendations/{exp_id}/verification")
            assert verif_res.status_code == 200
            assert verif_res.json()["policy_verdict"] == "VERIFIED"

            # 3. Deploy without approval -> 403 Forbidden
            deploy_fail = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert deploy_fail.status_code == 403

            # 4. Approve
            appr_res = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Approved by team lead"},
            )
            assert appr_res.status_code == 200
            assert appr_res.json()["action"] == "APPROVE"

            # 5. Deploy after approval -> 201 Created
            deploy_ok = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert deploy_ok.status_code == 201
            canary_id = deploy_ok.json()["id"]

            # 6. Get deployment status
            dep_status = await client.get(f"/api/v1/deployments/{canary_id}")
            assert dep_status.status_code == 200
            assert dep_status.json()["status"] == "RUNNING"

            # 7. List experiments
            list_res = await client.get("/api/v1/experiments")
            assert list_res.status_code == 200
            assert len(list_res.json()) >= 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_human_approval_rbac_blocks_unauthorized_roles(simulation_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with simulation_db() as db:
        user = User(id=user_id, email="viewer@example.com", hashed_password="pw", role="viewer", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="RBAC DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="rbacdb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            connection_id=connection_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_rbac_test ON users(id)",
            baseline_p95=100.0,
            candidate_p95=60.0,
            policy_verdict="VERIFIED",
            success=True,
            status="SIMULATED",
        )
        db.add_all([user, conn, exp])
        await db.commit()
        exp_id = exp.id

    async def override_db():
        async with simulation_db() as session:
            yield session

    async def override_viewer_user():
        return User(id=user_id, email="viewer@example.com", hashed_password="pw", role="viewer", is_active=True)

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = override_viewer_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Viewer attempts to approve -> 403 Forbidden
            appr_res = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Viewer attempting approval"},
            )
            assert appr_res.status_code == 403
            assert "not authorized" in appr_res.json()["detail"]

            # 2. Viewer attempts to reject -> 403 Forbidden
            rej_res = await client.post(
                f"/api/v1/recommendations/{exp_id}/reject",
                json={"action": "REJECT", "reason": "Viewer attempting rejection"},
            )
            assert rej_res.status_code == 403
            assert "not authorized" in rej_res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rejection_halts_pipeline(simulation_db):
    user_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    async with simulation_db() as db:
        user = User(id=user_id, email="dba@example.com", hashed_password="pw", role="dba", is_active=True)
        conn = DatabaseConnection(
            id=connection_id,
            user_id=user_id,
            name="Rejection DB",
            encrypted_connection_string="enc",
            host="localhost",
            port=5432,
            database_name="rejdb",
            username="postgres",
            is_active=True,
        )
        exp = OptimizationExperiment(
            connection_id=connection_id,
            timestamp=datetime.now(timezone.utc),
            strategy="CREATE_INDEX",
            candidate_sql="CREATE INDEX CONCURRENTLY idx_rej_test ON users(id)",
            baseline_p95=100.0,
            candidate_p95=60.0,
            policy_verdict="VERIFIED",
            success=True,
            status="SIMULATED",
        )
        db.add_all([user, conn, exp])
        await db.commit()

        # Reject recommendation
        rejection = await simulation_service.reject_recommendation(
            exp.id, user=user, reason="Candidate not needed", db=db
        )
        assert rejection.action == "REJECT"

        await db.refresh(exp)
        assert exp.status == "REJECTED"
        assert exp.success is False

        # Attempting deploy after rejection must fail
        with pytest.raises(PermissionError, match="Human approval required"):
            await simulation_service.deploy_canary(exp.id, user_id, db)

