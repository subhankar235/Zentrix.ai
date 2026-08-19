"""
Approval SQLAlchemy ORM Models for production deployment gates.
Reference: PRD.md §9, §13 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.experiment import OptimizationExperiment


class Approval(Base):
    """
    Human approval / rejection record required before production modification.
    """
    __tablename__ = "approvals"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # APPROVE, REJECT
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    experiment: Mapped["OptimizationExperiment"] = relationship(
        "OptimizationExperiment",
        back_populates="approvals",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="approvals",
    )
