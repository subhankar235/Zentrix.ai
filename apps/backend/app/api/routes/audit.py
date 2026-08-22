"""Audit Logging & Observability API Endpoints.

Reference: PRD.md §14, §15, §22 & ARCHITECTURE.md §4
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, CanaryRunOut
from app.services.audit_service import audit_service

router = APIRouter(tags=["Audit & Observability"])


@router.get("/audit/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    connection_id: Optional[uuid.UUID] = Query(None, description="Filter by database connection ID"),
    action_type: Optional[str] = Query(None, description="Filter by action type (e.g. CANARY_START, DDL_APPLIED, RECOMMENDATION_APPROVED)"),
    target_entity: Optional[str] = Query(None, description="Filter by target entity type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Retrieve immutable audit trail records with optional entity and action filters."""
    return await audit_service.list_audit_logs(
        db=db,
        connection_id=connection_id,
        user_id=None,
        action_type=action_type,
        target_entity=target_entity,
        limit=limit,
        offset=offset,
    )


@router.get("/connections/{connectionId}/audit-logs", response_model=AuditLogListResponse)
async def get_connection_audit_logs(
    connectionId: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Retrieve audit trail logs for a specific database connection."""
    return await audit_service.list_audit_logs(
        db=db,
        connection_id=connectionId,
        limit=limit,
        offset=offset,
    )


@router.get("/audit/canary-runs", response_model=list[CanaryRunOut])
async def list_canary_deployment_runs(
    connection_id: Optional[uuid.UUID] = Query(None, description="Filter by database connection ID"),
    experiment_id: Optional[uuid.UUID] = Query(None, description="Filter by experiment ID"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """Retrieve live canary deployment execution records and metrics."""
    return await audit_service.list_canary_runs(
        db=db,
        connection_id=connection_id,
        experiment_id=experiment_id,
        limit=limit,
    )
