"""Audit Log and Observability Pydantic Schemas.

Reference: PRD.md §13, §14, §15 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogBase(BaseModel):
    action_type: str = Field(..., description="Action name (e.g. USER_LOGIN, CANARY_START, CANARY_COMMIT, CANARY_ROLLBACK, DDL_APPLIED, DIAGNOSIS_GENERATED)")
    target_entity: str
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    user_id: Optional[uuid.UUID] = None
    connection_id: Optional[uuid.UUID] = None


class AuditLogOut(AuditLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    connection_id: Optional[uuid.UUID] = None
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogOut] = Field(default_factory=list)


class CanaryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    connection_id: uuid.UUID
    status: str
    canary_sql_applied: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    observation_window_minutes: int
    baseline_metrics: Optional[Dict[str, Any]] = None
    canary_metrics: Optional[Dict[str, Any]] = None
    rollback_reason: Optional[str] = None
