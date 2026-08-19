"""
Audit Log and Canary Run SQLAlchemy ORM Models.
Reference: PRD.md §13, §14 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.connection import DatabaseConnection
    from app.models.experiment import OptimizationExperiment


class AuditLog(Base):
    """
    Immutable audit trail for all security, authentication, and database-modifying events.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("database_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # e.g., USER_LOGIN, CANARY_START, CANARY_COMMIT, CANARY_ROLLBACK, DDL_APPLIED
    target_entity: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    target_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
    )
    connection: Mapped[Optional["DatabaseConnection"]] = relationship(
        "DatabaseConnection",
        back_populates="audit_logs",
    )


class CanaryRun(Base, TimestampMixin):
    """
    Live canary observation window monitoring and auto-rollback / commit execution.
    """
    __tablename__ = "canary_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("optimization_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="RUNNING",
        nullable=False,
    )  # RUNNING, COMMITTED, ROLLED_BACK, FAILED
    canary_sql_applied: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    observation_window_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )
    baseline_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    canary_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    rollback_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    experiment: Mapped["OptimizationExperiment"] = relationship(
        "OptimizationExperiment",
        back_populates="canary_runs",
    )
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="canary_runs",
    )
