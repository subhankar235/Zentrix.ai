"""Forecasting & Model Performance API Endpoints.

Reference: PRD.md §5 Feature 3, §12 & ARCHITECTURE.md §1, §4, §10
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.forecast import (
    ForecastResponse,
    ModelPerformanceResponse,
)
from app.services.forecast_service import forecast_service

router = APIRouter(tags=["Forecasting & Model Performance"])


@router.get("/forecast/{connectionId}", response_model=ForecastResponse)
@router.get("/connections/{connectionId}/forecasts", response_model=ForecastResponse)
async def get_connection_forecast(
    connectionId: uuid.UUID,
    query_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Get 7-day degradation risk forecast and probability curve for queries on a database connection."""
    try:
        return await forecast_service.generate_forecast(
            connection_id=connectionId,
            query_id=query_id,
            db=db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/models/performance", response_model=ModelPerformanceResponse)
async def get_models_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Retrieve model evaluation metrics: MAE over time, calibration score, and Evidently drift reports."""
    try:
        return await forecast_service.get_model_performance(db=db)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/forecasts/{id}/stream")
async def stream_forecast_progress(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EventSourceResponse:
    """Server-Sent Events (SSE) streaming live forecast horizon computation."""
    async def sse_event_stream() -> AsyncGenerator[dict[str, Any], None]:
        async for event in forecast_service.stream_forecast_execution(connection_id=id, db=db):
            yield {
                "event": event.get("event", "forecast_progress"),
                "data": json.dumps(event.get("data", {})),
            }

    return EventSourceResponse(sse_event_stream())
