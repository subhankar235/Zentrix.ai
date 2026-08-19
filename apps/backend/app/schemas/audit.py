"""
Audit Log Pydantic Schemas.
Reference: PRD.md §13, §14 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogBase(BaseModel):
    action_type: str = Field(..., description="Action name (e.g. USER_LOGIN, CANARY_START, DDL_APPLIED)")
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
