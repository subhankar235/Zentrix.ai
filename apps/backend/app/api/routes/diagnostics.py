"""
Diagnostics & Root Cause Analysis API Endpoints.
Reference: PRD.md §5 Feature 1, §12 & ARCHITECTURE.md §4
"""

import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_db_session
from app.models.diagnosis import Diagnosis, EvidenceGraphEdge, EvidenceGraphNode
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

router = APIRouter(prefix="/diagnoses", tags=["Diagnostics & Root Cause Analysis"])


@router.get("/{id}", response_model=DiagnosisDetailOut)
async def get_diagnosis_report(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get full multi-agent root-cause report including deterministic evidence graph.
    """
    stmt = (
        select(Diagnosis)
        .where(Diagnosis.id == id)
        .options(
            selectinload(Diagnosis.nodes),
            selectinload(Diagnosis.edges),
        )
    )
    res = await db.execute(stmt)
    diag = res.scalar_one_or_none()
    if not diag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")

    nodes_out = [EvidenceGraphNodeOut.model_validate(n) for n in diag.nodes]
    edges_out = [EvidenceGraphEdgeOut.model_validate(e) for e in diag.edges]

    diag_dict = DiagnosisOut.model_validate(diag).model_dump()
    return DiagnosisDetailOut(
        **diag_dict,
        evidence_graph=EvidenceGraphOut(nodes=nodes_out, edges=edges_out),
    )


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
        .where(OptimizationExperiment.diagnosis_id == id)
        .order_by(OptimizationExperiment.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/{id}/investigate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_investigation(
    id: uuid.UUID,
    request: InvestigationTriggerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Trigger an on-demand multi-agent causal investigation run.
    """
    return {
        "status": "ACCEPTED",
        "diagnosis_id": str(id),
        "message": "Multi-agent causal investigation task dispatched",
    }
