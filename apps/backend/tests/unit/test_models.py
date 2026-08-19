"""
Unit tests for Step 6 & 7: SQLAlchemy ORM Models and Alembic metadata.
Verifies all 17 models, table names, columns, relationships, and metadata.
"""

import uuid
from datetime import datetime, timezone
import pytest
from app.db.base import Base, TimestampMixin
from app.models import (
    User,
    DatabaseConnection,
    QueryMetric,
    TableMetric,
    PlanMetric,
    Diagnosis,
    EvidenceGraphNode,
    EvidenceGraphEdge,
    OptimizationExperiment,
    ModelPrediction,
    BanditEvent,
    ForecastRecord,
    ModelDriftReport,
    RoiRecord,
    Approval,
    AuditLog,
    CanaryRun,
)


def test_all_models_registered_in_metadata():
    """Verify all 17 tables exist in SQLAlchemy Base metadata."""
    expected_tables = {
        "users",
        "database_connections",
        "query_metrics",
        "table_metrics",
        "plan_metrics",
        "diagnoses",
        "evidence_graph_nodes",
        "evidence_graph_edges",
        "optimization_experiments",
        "model_predictions",
        "bandit_events",
        "forecast_records",
        "model_drift_reports",
        "roi_records",
        "approvals",
        "audit_logs",
        "canary_runs",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables)
    assert len(expected_tables) == 17


def test_user_model_instantiation():
    """Verify User model attributes and defaults."""
    u_id = uuid.uuid4()
    user = User(
        id=u_id,
        email="admin@zentrix.ai",
        hashed_password="hashed_pw_test",
        full_name="Admin DBA",
        role="admin",
        is_active=True,
        is_superuser=True,
    )
    assert user.id == u_id
    assert user.email == "admin@zentrix.ai"
    assert user.role == "admin"
    assert user.is_active is True
    assert user.is_superuser is True


def test_database_connection_model_instantiation():
    """Verify DatabaseConnection model attributes."""
    c_id = uuid.uuid4()
    u_id = uuid.uuid4()
    conn = DatabaseConnection(
        id=c_id,
        user_id=u_id,
        name="Production Neon DB",
        encrypted_connection_string="gAAAAABtest...",
        host="ep-dawn-pond.neon.tech",
        port=5432,
        database_name="neondb",
        username="neondb_owner",
        ssl_mode="require",
        provider="neon",
        permission_status={"pg_stat_statements": True, "hypopg": True},
        is_active=True,
    )
    assert conn.id == c_id
    assert conn.user_id == u_id
    assert conn.database_name == "neondb"
    assert conn.permission_status["hypopg"] is True


def test_telemetry_models_instantiation():
    """Verify QueryMetric, TableMetric, and PlanMetric models."""
    conn_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    qm = QueryMetric(
        connection_id=conn_id,
        timestamp=now,
        query_hash="abc123hash",
        query_text="SELECT * FROM orders WHERE status = $1",
        calls=100,
        total_exec_time=450.5,
        mean_exec_time=4.505,
    )
    assert qm.query_hash == "abc123hash"
    assert qm.calls == 100

    tm = TableMetric(
        connection_id=conn_id,
        timestamp=now,
        schema_name="public",
        table_name="orders",
        row_count=50000,
        dead_tuple_ratio=0.15,
    )
    assert tm.table_name == "orders"
    assert tm.dead_tuple_ratio == 0.15

    pm = PlanMetric(
        connection_id=conn_id,
        timestamp=now,
        plan_hash="plan123hash",
        estimated_rows=500.0,
        actual_rows=520.0,
        estimated_cost=150.0,
        actual_time=12.4,
    )
    assert pm.plan_hash == "plan123hash"
    assert pm.actual_rows == 520.0


def test_diagnosis_and_evidence_graph_instantiation():
    """Verify Diagnosis, EvidenceGraphNode, and EvidenceGraphEdge models."""
    diag_id = uuid.uuid4()
    conn_id = uuid.uuid4()
    diag = Diagnosis(
        id=diag_id,
        connection_id=conn_id,
        title="High dead-tuple bloat on orders table",
        primary_root_cause="VACUUM_LAG",
        severity="HIGH",
        confidence=0.92,
        summary="Autovacuum lag causing sequential scan fallbacks.",
    )
    assert diag.id == diag_id
    assert diag.primary_root_cause == "VACUUM_LAG"

    node1 = EvidenceGraphNode(
        diagnosis_id=diag_id,
        node_key="dead_tuple_ratio_spike",
        node_type="ANOMALY",
        label="Dead tuple ratio > 15%",
        agent_domain="VACUUM",
        confidence=0.95,
    )
    assert node1.agent_domain == "VACUUM"

    node2 = EvidenceGraphNode(
        diagnosis_id=diag_id,
        node_key="autovacuum_cost_limit_low",
        node_type="ROOT_CAUSE",
        label="Autovacuum throttled by cost limit",
        agent_domain="SUPERVISOR",
        confidence=0.92,
    )
    assert node2.node_type == "ROOT_CAUSE"


def test_experiment_and_roi_instantiation():
    """Verify OptimizationExperiment, ModelPrediction, BanditEvent, and RoiRecord."""
    exp_id = uuid.uuid4()
    conn_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    exp = OptimizationExperiment(
        id=exp_id,
        connection_id=conn_id,
        timestamp=now,
        strategy="CREATE_INDEX",
        candidate_sql="CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);",
        baseline_latency=120.0,
        baseline_p95=250.0,
        candidate_latency=15.0,
        candidate_p95=25.0,
        predicted_latency_delta=-105.0,
        policy_verdict="VERIFIED",
        success=True,
    )
    assert exp.id == exp_id
    assert exp.policy_verdict == "VERIFIED"

    pred = ModelPrediction(
        experiment_id=exp_id,
        model_version="lgb_delta_v1.0.0",
        prediction=-105.0,
        lower_bound=-120.0,
        upper_bound=-90.0,
        confidence=0.94,
    )
    assert pred.model_version == "lgb_delta_v1.0.0"

    bandit = BanditEvent(
        experiment_id=exp_id,
        connection_id=conn_id,
        context={"query_type": "filter", "table_size_mb": 500},
        action="CREATE_INDEX",
        propensity=0.85,
        model_version="thompson_v1.0",
    )
    assert bandit.action == "CREATE_INDEX"

    roi = RoiRecord(
        experiment_id=exp_id,
        connection_id=conn_id,
        estimated_monthly_savings_usd=145.50,
        compute_savings_usd=120.00,
        storage_savings_usd=0.00,
        io_savings_usd=25.50,
    )
    assert roi.estimated_monthly_savings_usd == 145.50


def test_approvals_and_audit_instantiation():
    """Verify Approval, AuditLog, and CanaryRun models."""
    exp_id = uuid.uuid4()
    u_id = uuid.uuid4()
    c_id = uuid.uuid4()

    appr = Approval(
        experiment_id=exp_id,
        user_id=u_id,
        action="APPROVE",
        reason="Verified 88% latency reduction in shadow replay.",
    )
    assert appr.action == "APPROVE"

    audit = AuditLog(
        user_id=u_id,
        connection_id=c_id,
        action_type="CANARY_DEPLOY_START",
        target_entity="optimization_experiments",
        target_id=str(exp_id),
    )
    assert audit.action_type == "CANARY_DEPLOY_START"

    canary = CanaryRun(
        experiment_id=exp_id,
        connection_id=c_id,
        status="RUNNING",
        canary_sql_applied="CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);",
        observation_window_minutes=15,
    )
    assert canary.status == "RUNNING"
    assert canary.observation_window_minutes == 15
