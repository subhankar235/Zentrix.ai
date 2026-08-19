"""
ROI and Cost-to-Dollar Calculation SQLAlchemy ORM Models.
Reference: PRD.md §5 Feature 4, §13 & ARCHITECTURE.md §7
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import Float, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.connection import DatabaseConnection
    from app.models.experiment import OptimizationExperiment


class RoiRecord(Base, TimestampMixin):
    """
    Dollar ROI translation record computed deterministically from verified experiment deltas.
    """
    __tablename__ = "roi_records"

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
    estimated_monthly_savings_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    compute_savings_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    storage_savings_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    io_savings_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    assumed_pricing_tier: Mapped[str] = mapped_column(
        String(100),
        default="standard",
        nullable=False,
    )
    frequency_per_day: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    calculation_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )

    # Relationships
    experiment: Mapped["OptimizationExperiment"] = relationship(
        "OptimizationExperiment",
        back_populates="roi_records",
    )
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="roi_records",
    )
