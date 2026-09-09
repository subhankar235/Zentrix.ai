"""
Optimization Experiments, Simulation, Verification, Approvals & Canary Stream Endpoints.
Reference: PRD.md §5 Feature 2, §9, §12 & ARCHITECTURE.md §1, §4, §10
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_connection_user, get_db_session
from app.core.config import get_settings
from app.core.exceptions import ShadowDBProvisioningError
from app.core.logging import get_logger
from app.db.customer_db import customer_connection_manager
from app.models.approval import Approval
from app.models.audit import AuditLog, CanaryRun
from app.models.connection import DatabaseConnection
from app.models.diagnosis import Diagnosis
from app.models.experiment import OptimizationExperiment
from app.models.user import User
from app.schemas.experiment import (
    ApprovalBase,
    ApprovalOut,
    CanaryRunOut,
    ExperimentVerificationOut,
    OptimizationExperimentOut,
    DevCanaryFixtureRequest,
    SimulationTriggerRequest,
)
from app.services.simulation_service import simulation_service, validate_canary_sql
from app.services.recommendation_service import recommendations_for_diagnosis
from app.services.roi_service import roi_service
from app.workers.canary_monitor import monitor_canary_tick
from app.tools.shadow_db_tool import ShadowProvisioningError

router = APIRouter(tags=["Optimization Experiments & Verifications"])
logger = get_logger(__name__)


# ─── Experiments Audit Trail ──────────────────────────────────────────────────

@router.get("/experiments", response_model=List[OptimizationExperimentOut])
async def list_experiments(
    connection_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    List optimization experiments and shadow replay verification audit logs.
    """
    return await simulation_service.list_experiments(
        db=db,
        connection_id=connection_id,
        limit=limit,
        owner_user_id=current_user.id,
        owner_is_superuser=current_user.is_superuser,
    )


@router.post("/experiments/dev/seed-canary", response_model=OptimizationExperimentOut, status_code=status.HTTP_201_CREATED)
async def seed_dev_canary_fixture(
    request: DevCanaryFixtureRequest,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Create a local-only committed canary fixture with a deterministic ROI record."""
    if not get_settings().is_development:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Development fixture not available")

    conn_stmt = select(DatabaseConnection).where(
        DatabaseConnection.id == request.connection_id,
        DatabaseConnection.is_active.is_(True),
    )
    if not current_user.is_superuser:
        conn_stmt = conn_stmt.where(DatabaseConnection.user_id == current_user.id)
    connection = await db.scalar(conn_stmt)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

    validate_canary_sql(request.candidate_sql)
    now = datetime.now(timezone.utc)
    experiment = OptimizationExperiment(
        connection_id=connection.id,
        timestamp=now,
        strategy="ANALYZE",
        candidate_sql=request.candidate_sql,
        baseline_latency=100.0,
        baseline_p95=120.0,
        candidate_latency=90.0,
        candidate_p95=110.0,
        baseline_cpu=0.60,
        candidate_cpu=0.20,
        baseline_io=3000.0,
        candidate_io=500.0,
        statistical_significance=True,
        confidence_interval_low=-1.0,
        confidence_interval_high=-0.1,
        skeptic_findings={
            "fixture": True,
            "note": "Development-only canary fixture",
            "fixture_metrics": {
                "p50_ms": 40.0,
                "p95_ms": 110.0,
                "p99_ms": 180.0,
                "query_count": 5,
                "error_rate": 0.0,
                "lock_wait_count": 0,
            },
        },
        policy_verdict="VERIFIED",
        success=True,
        risk="LOW",
        status="DEPLOYED",
    )
    db.add(experiment)
    await db.flush()

    canary_run = CanaryRun(
        experiment_id=experiment.id,
        connection_id=connection.id,
        status="COMMITTED",
        canary_sql_applied=request.candidate_sql,
        started_at=now,
        completed_at=now,
        observation_window_minutes=1,
        baseline_metrics={"p95_ms": 120.0, "p50_ms": 70.0, "error_rate": 0.0},
        canary_metrics={"p95_ms": 110.0, "p50_ms": 60.0, "error_rate": 0.0},
    )
    db.add(canary_run)
    db.add(AuditLog(
        user_id=current_user.id,
        connection_id=connection.id,
        action_type="DEV_CANARY_FIXTURE_CREATED",
        target_entity="optimization_experiment",
        target_id=str(experiment.id),
        details={"candidate_sql": request.candidate_sql},
        timestamp=now,
    ))
    await roi_service.calculate_and_save_experiment_roi(
        experiment_id=experiment.id,
        db=db,
    )
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.get("/experiments/{id}", response_model=OptimizationExperimentOut)
async def get_experiment(
    id: uuid.UUID,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get experiment details by ID.
    """
    exp = await simulation_service.get_experiment(
        experiment_id=id,
        db=db,
        owner_user_id=current_user.id,
        owner_is_superuser=current_user.is_superuser,
    )
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return exp


# ─── Simulation & Verification Workflow ───────────────────────────────────────

@router.post("/recommendations/{id}/simulate", response_model=OptimizationExperimentOut, status_code=status.HTTP_202_ACCEPTED)
@router.post("/experiments/simulate", response_model=OptimizationExperimentOut, status_code=status.HTTP_202_ACCEPTED)
async def simulate_recommendation(
    request: SimulationTriggerRequest,
    id: Optional[uuid.UUID] = None,
    connection_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Dispatch shadow DB simulation and replay workload against candidate optimization.
    """
    conn_stmt = select(DatabaseConnection).where(DatabaseConnection.id == request.connection_id)
    if not current_user.is_superuser:
        conn_stmt = conn_stmt.where(DatabaseConnection.user_id == current_user.id)
    conn = await db.scalar(conn_stmt)
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

    candidate_sql = request.candidate_sql
    strategy = request.strategy
    table_name = request.table_name
    if request.diagnosis_id:
        diagnosis = await db.scalar(
            select(Diagnosis).where(Diagnosis.id == request.diagnosis_id)
        )
        if not diagnosis or diagnosis.connection_id != conn.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
        if not current_user.is_superuser and diagnosis.connection_id != conn.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
        recommendations = await recommendations_for_diagnosis(diagnosis, db)
        recommendation = next((item for item in recommendations if item.id == id), None) if id else None
        if not recommendation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
        candidate_sql = recommendation.candidate_sql
        strategy = {"INDEX": "CREATE_INDEX", "STATISTICS": "ANALYZE", "VACUUM": "VACUUM"}.get(
            recommendation.type,
            request.strategy,
        )
        table_name = table_name or recommendation.table_name

    candidate_data = {
        "candidate_sql": candidate_sql,
        "strategy": strategy,
        "table_name": table_name,
        "query_id": request.query_id,
    }

    try:
        experiment = await simulation_service.run_simulation(
            connection_id=conn.id,
            candidate_data=candidate_data,
            db=db,
            diagnosis_id=request.diagnosis_id,
            workload=None,
        )
        return experiment
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ShadowProvisioningError as exc:
        logger.warning("Shadow database provisioning failed during recommendation simulation: %s", exc)
        raise ShadowDBProvisioningError(str(exc)) from exc
    except RuntimeError as exc:
        logger.error("Recommendation simulation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/recommendations/{id}/verification", response_model=ExperimentVerificationOut)
async def get_recommendation_verification(
    id: uuid.UUID,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Retrieve statistical verification result, Skeptic agent critiques, and deterministic policy verdict.
    """
    try:
        exp = await simulation_service.get_experiment(
            experiment_id=id,
            db=db,
            owner_user_id=current_user.id,
            owner_is_superuser=current_user.is_superuser,
        )
        if not exp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
        return await simulation_service.get_verification(experiment_id=id, db=db)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ─── Human Approvals & Deployment ────────────────────────────────────────────

@router.post("/recommendations/{id}/approve", response_model=ApprovalOut)
async def approve_recommendation(
    id: uuid.UUID,
    approval_in: Optional[ApprovalBase] = None,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Submit human approval to advance verified optimization candidate to production canary deployment.
    Enforces RBAC role authorization (DBA, Admin, Engineer, Lead).
    """
    try:
        return await simulation_service.approve_recommendation(
            experiment_id=id,
            user=current_user,
            reason=approval_in.reason if approval_in else None,
            db=db,
            owner_is_superuser=current_user.is_superuser,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/recommendations/{id}/reject", response_model=ApprovalOut)
async def reject_recommendation(
    id: uuid.UUID,
    rejection_in: Optional[ApprovalBase] = None,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Reject recommendation and feed negative reward into contextual bandit.
    Enforces RBAC role authorization (DBA, Admin, Engineer, Lead).
    """
    try:
        return await simulation_service.reject_recommendation(
            experiment_id=id,
            user=current_user,
            reason=rejection_in.reason if rejection_in else None,
            db=db,
            owner_is_superuser=current_user.is_superuser,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc




@router.post("/experiments/{id}/deploy", response_model=CanaryRunOut, status_code=status.HTTP_201_CREATED)
async def deploy_canary_experiment(
    id: uuid.UUID,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Trigger guarded canary deployment for a verified, approved optimization candidate.
    """
    try:
        exp = await simulation_service.get_experiment(
            experiment_id=id,
            db=db,
            owner_user_id=current_user.id,
            owner_is_superuser=current_user.is_superuser,
        )
        if not exp:
            raise LookupError(f"Experiment {id} not found")
        if exp.policy_verdict not in {"VERIFIED", "APPROVE"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot deploy candidate with policy verdict '{exp.policy_verdict}'. Must be VERIFIED.",
            )
        approval = await db.scalar(
            select(Approval).where(
                Approval.experiment_id == exp.id,
                Approval.action == "APPROVE",
            )
        )
        if not approval:
            raise PermissionError(
                f"Human approval required before production canary deployment. "
                f"No 'APPROVE' record found for experiment {id}."
            )
        is_dev_fixture = bool((exp.skeptic_findings or {}).get("fixture"))
        if is_dev_fixture and get_settings().is_development:
            return await simulation_service.deploy_canary(
                experiment_id=id,
                user_id=current_user.id,
                db=db,
                customer_connection=None,
                owner_is_superuser=current_user.is_superuser,
            )
        pool = await customer_connection_manager.get_customer_pool(exp.connection_id, db)
        async with pool.acquire() as customer:
            return await simulation_service.deploy_canary(
                experiment_id=id,
                user_id=current_user.id,
                db=db,
                customer_connection=customer,
                owner_is_superuser=current_user.is_superuser,
            )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/deployments/{id}", response_model=CanaryRunOut)
async def get_deployment_status(
    id: uuid.UUID,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Retrieve live canary deployment state, observation window progress, and auto-rollback state.
    """
    stmt = (
        select(CanaryRun)
        .join(OptimizationExperiment, OptimizationExperiment.id == CanaryRun.experiment_id)
        .join(DatabaseConnection, DatabaseConnection.id == OptimizationExperiment.connection_id)
        .where(CanaryRun.id == id)
    )
    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    canary = res.scalar_one_or_none()
    if not canary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment run not found")
    return canary


# ─── Server-Sent Events (SSE) Live Streams ───────────────────────────────────

@router.get("/experiments/{id}/canary/stream")
async def stream_canary_metrics(
    id: uuid.UUID,
    current_user: User = Depends(get_connection_user),
    db: AsyncSession = Depends(get_db_session),
) -> EventSourceResponse:
    """
    Server-Sent Events (SSE) endpoint streaming real-time canary metrics, latency delta, and auto-rollback status.
    Reference: ARCHITECTURE.md §1 & §10
    """
    owned = await db.scalar(
        select(CanaryRun)
        .join(OptimizationExperiment, OptimizationExperiment.id == CanaryRun.experiment_id)
        .join(DatabaseConnection, DatabaseConnection.id == OptimizationExperiment.connection_id)
        .where(
            CanaryRun.experiment_id == id,
            (DatabaseConnection.user_id == current_user.id) if not current_user.is_superuser else True,
        )
    )
    if not owned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canary run not found")

    async def event_generator() -> AsyncGenerator[dict, None]:
        while True:
            current = await db.scalar(
                select(CanaryRun)
                .where(CanaryRun.id == owned.id)
                .execution_options(populate_existing=True)
            )
            if not current:
                return
            metrics = current.canary_metrics or {}
            yield {
                "event": "canary_metric",
                "data": json.dumps({
                    "experiment_id": str(id),
                    "status": current.status,
                    "metrics": metrics,
                    "rollback_triggered": current.status == "ROLLED_BACK",
                }),
            }
            if current.status != "RUNNING":
                yield {
                    "event": "canary_completed",
                    "data": json.dumps({
                        "experiment_id": str(id),
                        "status": current.status,
                        "rollback_reason": current.rollback_reason,
                    }),
                }
                return
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
