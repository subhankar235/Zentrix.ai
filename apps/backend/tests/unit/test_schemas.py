"""
Unit tests for Step 9: Pydantic schemas validation.
Tests I/O contract serialization, nested evidence graphs, and PRD-matching structures.
"""

import uuid
from datetime import datetime, timezone
import pytest
from app.schemas import (
    UserCreate,
    UserOut,
    ConnectionCreate,
    ConnectionOut,
    QueryMetricCreate,
    QueryMetricOut,
    TableMetricCreate,
    TableMetricOut,
    PlanMetricCreate,
    PlanMetricOut,
    TelemetrySummaryResponse,
    EvidenceGraphNodeOut,
    EvidenceGraphEdgeOut,
    EvidenceGraphOut,
    DiagnosisOut,
    DiagnosisDetailOut,
    OptimizationExperimentOut,
    ExperimentVerificationOut,
    DegradationCurvePoint,
    ForecastResponse,
    ModelPerformanceResponse,
    RoiRecordOut,
    RoiSummaryResponse,
)


def test_user_schemas():
    """Verify UserCreate and UserOut validation."""
    u_in = UserCreate(email="dba@zentrix.ai", password="SecretPassword123!", role="dba")
    assert u_in.email == "dba@zentrix.ai"
    assert u_in.role == "dba"

    now = datetime.now(timezone.utc)
    u_out = UserOut(
        id=uuid.uuid4(),
        email="dba@zentrix.ai",
        role="dba",
        is_active=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )
    assert u_out.is_active is True


def test_connection_schemas():
    """Verify ConnectionCreate and ConnectionOut validation."""
    c_in = ConnectionCreate(
        name="Production DB",
        host="ep-dawn-pond.neon.tech",
        port=5432,
        database_name="neondb",
        username="neondb_owner",
        password="secret_password",
    )
    assert c_in.port == 5432
    assert c_in.provider == "neon"


def test_diagnosis_detail_nested_schema():
    """Verify full root-cause report matching PRD.md Feature 1."""
    diag_id = uuid.uuid4()
    node1_id = uuid.uuid4()
    node2_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    node1 = EvidenceGraphNodeOut(
        id=node1_id,
        diagnosis_id=diag_id,
        node_key="dead_tuple_ratio",
        node_type="ANOMALY",
        label="Dead tuple ratio > 15%",
        agent_domain="VACUUM",
        confidence=0.95,
        created_at=now,
    )
    node2 = EvidenceGraphNodeOut(
        id=node2_id,
        diagnosis_id=diag_id,
        node_key="autovacuum_cost_limit",
        node_type="ROOT_CAUSE",
        label="Autovacuum throttled",
        agent_domain="SUPERVISOR",
        confidence=0.90,
        created_at=now,
    )
    edge = EvidenceGraphEdgeOut(
        id=uuid.uuid4(),
        diagnosis_id=diag_id,
        source_node_id=node2_id,
        target_node_id=node1_id,
        relation_type="CAUSES",
        weight=0.92,
        created_at=now,
    )

    graph = EvidenceGraphOut(nodes=[node1, node2], edges=[edge])
    detail = DiagnosisDetailOut(
        id=diag_id,
        connection_id=uuid.uuid4(),
        title="High Autovacuum Lag",
        primary_root_cause="VACUUM_LAG",
        contributing_factors=[{"factor": "cost_limit", "weight": 0.8}],
        severity="HIGH",
        confidence=0.92,
        summary="Autovacuum throttling leads to high dead tuple bloat.",
        validation_plan={"step": "shadow_replay"},
        status="DETECTED",
        created_at=now,
        updated_at=now,
        evidence_graph=graph,
    )
    assert detail.primary_root_cause == "VACUUM_LAG"
    assert len(detail.evidence_graph.nodes) == 2
    assert len(detail.evidence_graph.edges) == 1


def test_experiment_verification_schema():
    """Verify statistical verification schema matching PRD.md Feature 2."""
    verif = ExperimentVerificationOut(
        experiment_id=uuid.uuid4(),
        policy_verdict="VERIFIED",
        statistical_significance=True,
        p_value=0.002,
        confidence_interval=[-110.5, -88.0],
        skeptic_critiques=[{"check": "write_overhead", "status": "PASS"}],
        recommendation_summary="Verified 88% latency drop.",
        is_safe_for_canary=True,
    )
    assert verif.policy_verdict == "VERIFIED"
    assert verif.is_safe_for_canary is True


def test_forecast_and_roi_schemas():
    """Verify forecasting response and ROI summary schemas."""
    now = datetime.now(timezone.utc)
    curve_pt = DegradationCurvePoint(
        timestamp=now,
        predicted_probability=0.75,
        confidence_lower=0.60,
        confidence_upper=0.85,
    )
    forecast = ForecastResponse(
        connection_id=uuid.uuid4(),
        forecast_window_start=now,
        forecast_window_end=now,
        degradation_probability=0.75,
        is_flagged_for_action=True,
        curve=[curve_pt],
        suggested_strategies=["CREATE_INDEX"],
    )
    assert forecast.degradation_probability == 0.75

    roi_summary = RoiSummaryResponse(
        connection_id=uuid.uuid4(),
        total_monthly_savings_usd=350.0,
        total_compute_savings_usd=280.0,
        total_storage_savings_usd=20.0,
        total_io_savings_usd=50.0,
        optimizations_count=2,
        roi_breakdowns=[],
    )
    assert roi_summary.total_monthly_savings_usd == 350.0
