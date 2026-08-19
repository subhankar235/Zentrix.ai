"""
ROI & Cost-to-Dollar Calculation API Endpoints.
Reference: PRD.md §5 Feature 4, §12 & ARCHITECTURE.md §4
"""

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db_session
from app.models.roi import RoiRecord
from app.models.user import User
from app.schemas.roi import RoiRecordOut, RoiSummaryResponse

router = APIRouter(prefix="/roi", tags=["ROI & Cost-to-Dollar Calculation"])


@router.get("/{connectionId}", response_model=RoiSummaryResponse)
async def get_connection_roi_summary(
    connectionId: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get aggregate dollar savings and optimization breakdowns for a monitored connection.
    """
    stmt = (
        select(RoiRecord)
        .where(RoiRecord.connection_id == connectionId)
        .order_by(RoiRecord.created_at.desc())
    )
    res = await db.execute(stmt)
    roi_records = res.scalars().all()

    total_monthly = sum(r.estimated_monthly_savings_usd for r in roi_records)
    total_compute = sum(r.compute_savings_usd for r in roi_records)
    total_storage = sum(r.storage_savings_usd for r in roi_records)
    total_io = sum(r.io_savings_usd for r in roi_records)

    return RoiSummaryResponse(
        connection_id=connectionId,
        total_monthly_savings_usd=total_monthly,
        total_compute_savings_usd=total_compute,
        total_storage_savings_usd=total_storage,
        total_io_savings_usd=total_io,
        optimizations_count=len(roi_records),
        roi_breakdowns=[RoiRecordOut.model_validate(r) for r in roi_records],
    )


@router.get("/experiments/{experimentId}", response_model=RoiRecordOut)
async def get_experiment_roi(
    experimentId: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get specific ROI calculation details for an optimization experiment.
    """
    stmt = select(RoiRecord).where(RoiRecord.experiment_id == experimentId)
    res = await db.execute(stmt)
    roi = res.scalar_one_or_none()
    if not roi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ROI calculation not found")
    return roi
