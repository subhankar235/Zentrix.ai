"""
Database Connection ORM Models for monitored customer databases.
Reference: PRD.md §13, §14 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.telemetry import QueryMetric, TableMetric, PlanMetric
    from app.models.diagnosis import Diagnosis
    from app.models.experiment import OptimizationExperiment, BanditEvent
    from app.models.forecast import ForecastRecord
    from app.models.roi import RoiRecord
    from app.models.audit import AuditLog, CanaryRun


class DatabaseConnection(Base, TimestampMixin):
    """
    Monitored target database connection record.
    Stores encrypted credentials at rest and connection metadata.
    """
    __tablename__ = "database_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    encrypted_connection_string: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=5432,
        nullable=False,
    )
    database_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    __table_args__ = (
        Index(
            "uq_database_connections_owner_target",
            "user_id",
            func.lower(host),
            "port",
            func.lower(database_name),
            unique=True,
        ),
    )
    ssl_mode: Mapped[str] = mapped_column(
        String(50),
        default="require",
        nullable=False,
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        default="neon",
        nullable=True,
    )
    permission_status: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="connections",
    )
    query_metrics: Mapped[List["QueryMetric"]] = relationship(
        "QueryMetric",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    table_metrics: Mapped[List["TableMetric"]] = relationship(
        "TableMetric",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    plan_metrics: Mapped[List["PlanMetric"]] = relationship(
        "PlanMetric",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    diagnoses: Mapped[List["Diagnosis"]] = relationship(
        "Diagnosis",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    experiments: Mapped[List["OptimizationExperiment"]] = relationship(
        "OptimizationExperiment",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    bandit_events: Mapped[List["BanditEvent"]] = relationship(
        "BanditEvent",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    forecasts: Mapped[List["ForecastRecord"]] = relationship(
        "ForecastRecord",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    roi_records: Mapped[List["RoiRecord"]] = relationship(
        "RoiRecord",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    canary_runs: Mapped[List["CanaryRun"]] = relationship(
        "CanaryRun",
        back_populates="connection",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="connection",
    )
