"""
Optimization Experiment, Model Prediction, and Bandit Event ORM Models.
Reference: PRD.md §13 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.connection import DatabaseConnection
    from app.models.diagnosis import Diagnosis
    from app.models.roi import RoiRecord
    from app.models.approval import Approval
    from app.models.audit import CanaryRun


class OptimizationExperiment(Base, TimestampMixin):
    """
    Simulation experiment comparing baseline vs candidate query performance.
    """
    __tablename__ = "optimization_experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("diagnoses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    query_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )
    table_name: Mapped[Optional[str]] = mapped_column(
        String(63),
        nullable=True,
    )
    strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # CREATE_INDEX, DROP_INDEX, ANALYZE, REWRITE, CONFIG
    candidate_sql: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    baseline_latency: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    baseline_p95: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    baseline_cpu: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    baseline_io: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    candidate_latency: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    candidate_p95: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    candidate_cpu: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    candidate_io: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    predicted_latency_delta: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    actual_latency_delta: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    prediction_error: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    statistical_significance: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    confidence_interval_low: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    confidence_interval_high: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    skeptic_findings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    policy_verdict: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
    )  # VERIFIED, CONDITIONAL, REJECTED
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    risk: Mapped[str] = mapped_column(
        String(50),
        default="LOW",
        nullable=False,
    )  # LOW, MEDIUM, HIGH
    rollback: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
    )  # PENDING, SIMULATED, APPROVED, REJECTED, DEPLOYED, ROLLED_BACK

    # Relationships
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="experiments",
    )
    diagnosis: Mapped[Optional["Diagnosis"]] = relationship(
        "Diagnosis",
        back_populates="experiments",
    )
    predictions: Mapped[List["ModelPrediction"]] = relationship(
        "ModelPrediction",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    bandit_events: Mapped[List["BanditEvent"]] = relationship(
        "BanditEvent",
        back_populates="experiment",
    )
    roi_records: Mapped[List["RoiRecord"]] = relationship(
        "RoiRecord",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    canary_runs: Mapped[List["CanaryRun"]] = relationship(
        "CanaryRun",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[List["Approval"]] = relationship(
        "Approval",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ModelPrediction(Base):
    """
    ML model inference result and error tracking for closed-loop learning.
    """
    __tablename__ = "model_predictions"

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
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    prediction: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    lower_bound: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    upper_bound: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    actual: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    absolute_error: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    features_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    experiment: Mapped["OptimizationExperiment"] = relationship(
        "OptimizationExperiment",
        back_populates="predictions",
    )


class BanditEvent(Base):
    """
    Contextual Thompson Sampling bandit decision event for strategy selection.
    """
    __tablename__ = "bandit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    experiment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("optimization_experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    propensity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    reward: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    experiment: Mapped[Optional["OptimizationExperiment"]] = relationship(
        "OptimizationExperiment",
        back_populates="bandit_events",
    )
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="bandit_events",
    )
