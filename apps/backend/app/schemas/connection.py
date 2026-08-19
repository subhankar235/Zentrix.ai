"""
Database Connection Pydantic Schemas.
Reference: PRD.md §13, §14 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConnectionBase(BaseModel):
    name: str = Field(..., max_length=255, description="Human-readable connection name")
    host: str = Field(..., max_length=255, description="Database host (e.g., Neon endpoint)")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port")
    database_name: str = Field(..., max_length=255, description="Target database name")
    username: str = Field(..., max_length=255, description="Monitoring database user")
    ssl_mode: str = Field(default="require", description="SSL connection mode")
    provider: Optional[str] = Field(default="neon", description="Cloud/provider name (neon, rds, self-hosted)")


class ConnectionCreate(ConnectionBase):
    password: Optional[str] = Field(None, description="Password for database connection")
    connection_string: Optional[str] = Field(
        None,
        description="Full connection URI (if supplied, auto-populates host/port/user/pass)",
    )


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_mode: Optional[str] = None
    provider: Optional[str] = None
    is_active: Optional[bool] = None


class ConnectionOut(ConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    permission_status: Optional[Dict[str, Any]] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    success: bool = Field(..., description="Whether test connection succeeded")
    postgres_version: Optional[str] = Field(None, description="Server PostgreSQL version string")
    permissions: Dict[str, bool] = Field(
        default_factory=dict,
        description="Extension and system-view access status (pg_stat_statements, hypopg, etc.)",
    )
    latency_ms: Optional[float] = Field(None, description="Roundtrip ping latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if test failed")
