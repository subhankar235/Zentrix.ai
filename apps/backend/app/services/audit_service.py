"""Audit Logging & Observability Service.

Provides centralized helpers for recording immutable audit trail logs and
querying system audit records per PRD.md §14, §15, §22.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditLog, CanaryRun
from app.schemas.audit import AuditLogListResponse, AuditLogOut

logger = get_logger(__name__)


class AuditService:
    """Service managing audit trail records and query logging."""

    async def log_event(
        self,
        db: AsyncSession,
        action_type: str,
        target_entity: str,
        target_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        connection_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create and persist an immutable audit trail entry."""
        now = datetime.now(timezone.utc)
        entry = AuditLog(
            user_id=user_id,
            connection_id=connection_id,
            action_type=action_type,
            target_entity=target_entity,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
            timestamp=now,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        logger.info(
            f"Audit log created: action='{action_type}', entity='{target_entity}'",
            extra={
                "action": action_type,
                "target_entity": target_entity,
                "target_id": target_id,
                "connection_id": str(connection_id) if connection_id else None,
                "user_id": str(user_id) if user_id else None,
            },
        )
        return entry

    async def list_audit_logs(
        self,
        db: AsyncSession,
        connection_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        action_type: Optional[str] = None,
        target_entity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditLogListResponse:
        """Query and paginate audit logs with optional filters."""
        stmt = select(AuditLog)
        count_stmt = select(func.count(AuditLog.id))

        if connection_id is not None:
            stmt = stmt.where(AuditLog.connection_id == connection_id)
            count_stmt = count_stmt.where(AuditLog.connection_id == connection_id)
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
            count_stmt = count_stmt.where(AuditLog.user_id == user_id)
        if action_type is not None:
            stmt = stmt.where(AuditLog.action_type == action_type)
            count_stmt = count_stmt.where(AuditLog.action_type == action_type)
        if target_entity is not None:
            stmt = stmt.where(AuditLog.target_entity == target_entity)
            count_stmt = count_stmt.where(AuditLog.target_entity == target_entity)

        total = await db.scalar(count_stmt) or 0

        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
        res = await db.execute(stmt)
        items = list(res.scalars().all())

        return AuditLogListResponse(
            total=total,
            items=[AuditLogOut.model_validate(item) for item in items],
        )

    async def list_canary_runs(
        self,
        db: AsyncSession,
        connection_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
        limit: int = 20,
    ) -> List[CanaryRun]:
        """Query canary deployment history."""
        stmt = select(CanaryRun)
        if connection_id is not None:
            stmt = stmt.where(CanaryRun.connection_id == connection_id)
        if experiment_id is not None:
            stmt = stmt.where(CanaryRun.experiment_id == experiment_id)
        stmt = stmt.order_by(CanaryRun.started_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())


audit_service = AuditService()
