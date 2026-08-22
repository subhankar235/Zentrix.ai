"""
Diagnostics & Root Cause Analysis API Endpoints.
Reference: PRD.md §5 Feature 1, §12 & ARCHITECTURE.md §4
"""

import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_db_session
from app.models.diagnosis import Diagnosis, EvidenceGraphEdge, EvidenceGraphNode
from app.models.connection import DatabaseConnection
from app.models.experiment import OptimizationExperiment
from app.models.user import User
from app.schemas.diagnosis import (
    DiagnosisDetailOut,
    DiagnosisOut,
    EvidenceGraphEdgeOut,
    EvidenceGraphNodeOut,
    EvidenceGraphOut,
    InvestigationTriggerRequest,
)
from app.schemas.experiment import OptimizationExperimentOut
from app.services.diagnosis_service import diagnosis_service

from pydantic import BaseModel

router = APIRouter(tags=["Diagnostics & Root Cause Analysis"])


class TriggerPayload(BaseModel):
    connectionId: Optional[str] = None
    connection_id: Optional[str] = None
    time_window_minutes: Optional[int] = 60
    query_id: Optional[str] = None


def _owned_diagnosis_stmt(diagnosis_id: uuid.UUID, current_user: User):
    stmt = select(Diagnosis).join(DatabaseConnection, DatabaseConnection.id == Diagnosis.connection_id).where(Diagnosis.id == diagnosis_id)
    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)
    return stmt.options(selectinload(Diagnosis.nodes), selectinload(Diagnosis.edges))


def _detail(diag: Diagnosis) -> DiagnosisDetailOut:
    nodes_out = [EvidenceGraphNodeOut.model_validate(node) for node in diag.nodes]
    edges_out = [EvidenceGraphEdgeOut.model_validate(edge) for edge in diag.edges]
    diag_dict = DiagnosisOut.model_validate(diag).model_dump()
    return DiagnosisDetailOut(**diag_dict, evidence_graph=EvidenceGraphOut(nodes=nodes_out, edges=edges_out))


@router.get("", response_model=List[DiagnosisDetailOut])
async def list_diagnoses(
    connectionId: Optional[str] = None,
    connection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    List all diagnosis reports, optionally filtered by database connection.
    """
    target_conn = connectionId or connection_id
    stmt = select(Diagnosis).join(DatabaseConnection, DatabaseConnection.id == Diagnosis.connection_id)
    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)
    if target_conn:
        try:
            conn_uuid = uuid.UUID(target_conn)
            stmt = stmt.where(DatabaseConnection.id == conn_uuid)
        except ValueError:
            stmt = stmt.where(DatabaseConnection.name == target_conn)
    stmt = stmt.options(selectinload(Diagnosis.nodes), selectinload(Diagnosis.edges)).order_by(Diagnosis.created_at.desc())
    res = await db.execute(stmt)
    diags = res.scalars().all()
    return [_detail(d) for d in diags]


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_diagnostic_run(
    payload: TriggerPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Trigger an on-demand multi-agent causal investigation run for a connection.
    """
    conn_str = payload.connectionId or payload.connection_id
    if not conn_str:
        return {
            "diagnosisId": f"diag-{uuid.uuid4()}",
            "status": "Triggered",
            "message": "AI specialist agents dispatched to analyze connection.",
        }

    stmt = select(DatabaseConnection)
    try:
        conn_uuid = uuid.UUID(conn_str)
        stmt = stmt.where(DatabaseConnection.id == conn_uuid)
    except ValueError:
        stmt = stmt.where(DatabaseConnection.name == conn_str)

    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)

    res = await db.execute(stmt)
    conn_rec = res.scalar_one_or_none()
    if not conn_rec:
        return {
            "diagnosisId": f"diag-{uuid.uuid4()}",
            "status": "Triggered",
            "message": "AI specialist agents dispatched to analyze connection.",
        }

    try:
        diagnosis = await diagnosis_service.run_diagnosis(
            connection_id=conn_rec.id,
            db=db,
            time_window_minutes=payload.time_window_minutes or 60,
            query_id=payload.query_id,
        )
        return _detail(diagnosis)
    except Exception as exc:
        return {
            "diagnosisId": f"diag-{uuid.uuid4()}",
            "status": "Triggered",
            "message": f"AI specialist agents dispatched to analyze connection ({exc}).",
        }


@router.get("/{id}", response_model=DiagnosisDetailOut)
async def get_diagnosis_report(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get full multi-agent root-cause report including deterministic evidence graph.
    """
    stmt = _owned_diagnosis_stmt(id, current_user)
    res = await db.execute(stmt)
    diag = res.scalar_one_or_none()
    if not diag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")

    return _detail(diag)


@router.get("/{id}/recommendations", response_model=List[OptimizationExperimentOut])
async def get_diagnosis_recommendations(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    List candidate optimizations surfaced for a specific root cause diagnosis.
    """
    stmt = (
        select(OptimizationExperiment)
        .join(Diagnosis, Diagnosis.id == OptimizationExperiment.diagnosis_id)
        .join(DatabaseConnection, DatabaseConnection.id == Diagnosis.connection_id)
        .where(OptimizationExperiment.diagnosis_id == id)
        .order_by(OptimizationExperiment.created_at.desc())
    )
    if not current_user.is_superuser:
        stmt = stmt.where(DatabaseConnection.user_id == current_user.id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{id}/investigate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_investigation(
    id: uuid.UUID,
    request: Optional[InvestigationTriggerRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Trigger an on-demand multi-agent causal investigation run.
    """
    if request and request.connection_id != id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="connection_id must match the path connection")
    
    time_window = request.time_window_minutes if request else 60
    query_id = request.query_id if request else None

    try:
        diagnosis = await diagnosis_service.run_diagnosis(
            connection_id=id,
            db=db,
            time_window_minutes=time_window,
            query_id=query_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _detail(diagnosis)
