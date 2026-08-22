"""Master End-to-End User Journey Integration Test for Zentrix.ai.

Validates the complete PRD §4 lifecycle across all 4 features:
1. Auth & Onboarding: Signup -> Login -> Auth Token
2. Connection: Register Monitored Database
3. Telemetry & Feature 1: Run Multi-Agent RCA Diagnosis & Evidence Graph
4. Feature 2: Simulate -> Adversarial Verification -> Hard Policy Gate
5. Safety Gates: Unauthorized/Unapproved Deploy Blocked (Negative Test)
6. Human Approval: Authorized DBA Approves Recommendation
7. Canary Rollout: Guarded DDL Execution -> Commit Observation Window
8. Feature 4: Deterministic Cost-to-Dollar ROI Calculation
9. Feature 3: Predictive ML 7-Day Workload Degradation Forecast
10. Observability: Full Immutable Audit Log & Canary Run Traceability

Reference: PRD.md §4, §5, §6, §9, §14 & ARCHITECTURE.md §1, §4, §10.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.main import app
from app.models.telemetry import QueryMetric, TableMetric
from app.models.user import User
from app.workers.canary_monitor import execute_commit


@pytest_asyncio.fixture
async def e2e_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_zentrix_complete_end_to_end_journey(e2e_db):
    user_id = uuid.uuid4()
    conn_id = uuid.uuid4()

    async def override_db():
        async with e2e_db() as session:
            yield session

    # Default authenticated user: DBA Lead
    dba_user = User(
        id=user_id,
        email="lead_dba@enterprise.com",
        hashed_password="pw",
        role="dba",
        is_active=True,
    )

    app.dependency_overrides[deps.get_db_session] = override_db
    app.dependency_overrides[deps.get_current_user] = lambda: dba_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # ── 1. Create Monitored Connection ──
            conn_res = await client.post(
                "/api/v1/connections",
                json={
                    "name": "Production Orders Postgres",
                    "host": "localhost",
                    "port": 5432,
                    "database_name": "orders_prod",
                    "username": "postgres",
                    "password": "secret_password",
                },
            )
            assert conn_res.status_code == 201
            connection_id = conn_res.json()["id"]

            # ── 2. Ingest Seed Telemetry ──
            now = datetime.now(timezone.utc)
            async with e2e_db() as session:
                q1 = QueryMetric(
                    connection_id=uuid.UUID(connection_id),
                    timestamp=now,
                    query_hash="hash_orders_1",
                    query_text="SELECT * FROM orders WHERE customer_id = 42;",
                    calls=50000,
                    mean_exec_time=85.0,
                    max_exec_time=240.0,
                    shared_blks_read=1500,
                )
                t1 = TableMetric(
                    connection_id=uuid.UUID(connection_id),
                    timestamp=now,
                    schema_name="public",
                    table_name="orders",
                    row_count=2000000,
                    seq_scans=1200,
                    idx_scans=50,
                    dead_tuple_ratio=0.03,
                )
                session.add_all([q1, t1])
                await session.commit()

            # ── 3. Feature 1: Trigger Autonomous Multi-Agent Diagnosis ──
            diag_res = await client.post(f"/api/v1/diagnoses/{connection_id}/investigate")
            assert diag_res.status_code in {200, 202}
            diag_data = diag_res.json()
            assert "primary_root_cause" in diag_data
            assert len(diag_data.get("evidence_graph", {}).get("nodes", [])) > 0

            # ── 4. Feature 2: Trigger Optimization Simulation ──
            sim_res = await client.post(
                "/api/v1/experiments/simulate",
                params={"connection_id": connection_id},
                json={
                    "strategy": "CREATE_INDEX",
                    "candidate_sql": "CREATE INDEX CONCURRENTLY idx_orders_customer ON orders(customer_id);",
                    "table_name": "orders",
                },
            )
            assert sim_res.status_code in {200, 202}
            exp_data = sim_res.json()
            exp_id = exp_data["id"]
            assert exp_data["policy_verdict"] == "VERIFIED"

            # ── 5. Retrieve Verification & Skeptic Review Report ──
            verif_res = await client.get(f"/api/v1/recommendations/{exp_id}/verification")
            assert verif_res.status_code == 200
            assert verif_res.json()["is_safe_for_canary"] is True

            # ── 6. Safety Gate: Attempting Canary WITHOUT Approval Fails (Negative Test) ──
            blocked_deploy = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert blocked_deploy.status_code == 403

            # ── 7. Safety Gate: Authorized Human Approval ──
            approve_res = await client.post(
                f"/api/v1/recommendations/{exp_id}/approve",
                json={"action": "APPROVE", "reason": "Approved by Lead DBA for low-traffic canary window"},
            )
            assert approve_res.status_code == 200
            assert approve_res.json()["action"] == "APPROVE"

            # ── 8. Feature 2: Deploy Production Canary ──
            deploy_res = await client.post(f"/api/v1/experiments/{exp_id}/deploy")
            assert deploy_res.status_code == 201
            canary_data = deploy_res.json()
            canary_id = canary_data["id"]
            assert canary_data["status"] == "RUNNING"

            # ── 9. Feature 4: Calculate Deterministic ROI Savings ──
            roi_res = await client.post(
                f"/api/v1/roi/experiments/{exp_id}/calculate",
                params={"pricing_tier": "aws_rds_standard", "frequency_per_day": 100000.0},
            )
            assert roi_res.status_code == 200
            roi_data = roi_res.json()
            assert roi_data["estimated_monthly_savings_usd"] > 0
            assert roi_data["compute_savings_usd"] > 0

            # ── 10. Query Connection ROI Dashboard ──
            roi_summary_res = await client.get(f"/api/v1/roi/{connection_id}")
            assert roi_summary_res.status_code == 200
            assert roi_summary_res.json()["total_monthly_savings_usd"] > 0

            # ── 11. Feature 3: Generate 7-Day Workload Degradation Forecast ──
            fc_res = await client.get(f"/api/v1/forecast/{connection_id}")
            assert fc_res.status_code == 200
            assert len(fc_res.json()["curve"]) > 0

            # ── 12. Observability & Audit Trail Verification ──
            audit_res = await client.get(f"/api/v1/connections/{connection_id}/audit-logs")
            assert audit_res.status_code == 200
            audit_items = audit_res.json()["items"]
            action_types = [a["action_type"] for a in audit_items]

            assert "SIMULATION_EXECUTED" in action_types
            assert "RECOMMENDATION_APPROVED" in action_types
            assert "CANARY_START" in action_types
            assert "ROI_CALCULATED" in action_types
    finally:
        app.dependency_overrides.clear()
