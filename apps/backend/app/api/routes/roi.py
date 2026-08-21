"""ROI & Cost-to-Dollar Calculation API Endpoints.

Reference: PRD.md §5 Feature 4, §12 & ARCHITECTURE.md §4
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.roi import RoiRecordOut, RoiSummaryResponse
from app.services.roi_service import roi_service

router = APIRouter(prefix="/roi", tags=["ROI & Cost-to-Dollar Calculation"])


@router.get("/{connectionId}", response_model=RoiSummaryResponse)
async def get_connection_roi_summary(
    connectionId: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get aggregate dollar savings and optimization breakdowns for a monitored connection."""
    try:
        return await roi_service.get_connection_roi_summary(connection_id=connectionId, db=db)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/experiments/{experimentId}", response_model=RoiRecordOut)
async def get_experiment_roi(
    experimentId: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get specific ROI calculation details for an optimization experiment."""
    roi = await roi_service.get_experiment_roi(experiment_id=experimentId, db=db)
    if not roi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ROI calculation not found")
    return roi


@router.post("/experiments/{experimentId}/calculate", response_model=RoiRecordOut)
async def calculate_and_save_experiment_roi(
    experimentId: uuid.UUID,
    pricing_tier: str = Query(default="standard", description="Pricing tier: aws_rds_standard, neon_serverless, gcp_cloud_sql, standard"),
    frequency_per_day: float = Query(default=100_000.0, description="Estimated daily query executions"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Trigger deterministic ROI translation from measured experiment deltas and persist record."""
    try:
        return await roi_service.calculate_and_save_experiment_roi(
            experiment_id=experimentId,
            db=db,
            pricing_tier=pricing_tier,
            frequency_per_day=frequency_per_day,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
