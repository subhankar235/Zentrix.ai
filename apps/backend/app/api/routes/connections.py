"""
Database Connections API Endpoints.
Reference: PRD.md §12 & ARCHITECTURE.md §4
"""

import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.connection import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionTestResponse,
)
from app.schemas.diagnosis import DiagnosisOut
from app.schemas.telemetry import TelemetrySummaryResponse
from app.services.connection_service import connection_service
from sqlalchemy import select
from app.models.diagnosis import Diagnosis

router = APIRouter(prefix="/connections", tags=["Database Connections"])


@router.post("", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def register_connection(
    conn_in: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Register a new monitored target PostgreSQL connection.
    Encrypts connection credentials at rest and runs initial permission checks.
    """
    return await connection_service.create_connection(
        user_id=current_user.id,
        conn_in=conn_in,
        db=db,
    )


@router.get("", response_model=List[ConnectionOut])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    List all active monitored database connections owned by current user.
    """
    return await connection_service.list_connections(
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
        db=db,
    )


@router.get("/{id}", response_model=ConnectionOut)
async def get_connection(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Get monitored connection details by ID.
    """
    conn = await connection_service.get_connection(
        connection_id=id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
        db=db,
    )
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return conn


@router.post("/{id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Test target database reachability, credentials, and required extensions (pg_stat_statements, hypopg).
    """
    test_result = await connection_service.test_connection(
        connection_id=id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
        db=db,
    )
    if not test_result.success and test_result.error == "Database connection not found or unauthorized":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return test_result


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Delete / remove a monitored database connection.
    """
    deleted = await connection_service.delete_connection(
        connection_id=id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
        db=db,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")


@router.get("/{id}/telemetry", response_model=TelemetrySummaryResponse)
async def get_connection_telemetry(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Retrieve live/recent normalized telemetry metrics summary for a connected database.
    """
    summary = await connection_service.get_telemetry_summary(
        connection_id=id,
        user_id=current_user.id,
        is_superuser=current_user.is_superuser,
        db=db,
    )
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return summary


@router.get("/{id}/diagnoses", response_model=List[DiagnosisOut])
async def list_connection_diagnoses(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    List detected root-cause diagnoses for a given database connection.
    """
    stmt = (
        select(Diagnosis)
        .where(Diagnosis.connection_id == id)
        .order_by(Diagnosis.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()

