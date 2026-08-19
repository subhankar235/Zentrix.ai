"""
Diagnosis and Evidence Graph SQLAlchemy ORM Models.
Reference: PRD.md §13 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.connection import DatabaseConnection
    from app.models.experiment import OptimizationExperiment


class Diagnosis(Base, TimestampMixin):
    """
    Root cause diagnosis record created by Feature 1 Supervisor Agent.
    """
    __tablename__ = "diagnoses"

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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    primary_root_cause: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    contributing_factors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        default="MEDIUM",
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    validation_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="DETECTED",
        nullable=False,
    )

    # Relationships
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="diagnoses",
    )
    nodes: Mapped[List["EvidenceGraphNode"]] = relationship(
        "EvidenceGraphNode",
        back_populates="diagnosis",
        cascade="all, delete-orphan",
    )
    edges: Mapped[List["EvidenceGraphEdge"]] = relationship(
        "EvidenceGraphEdge",
        back_populates="diagnosis",
        cascade="all, delete-orphan",
    )
    experiments: Mapped[List["OptimizationExperiment"]] = relationship(
        "OptimizationExperiment",
        back_populates="diagnosis",
    )


class EvidenceGraphNode(Base):
    """
    Evidence graph node representing a metric, anomaly, hypothesis, or root cause.
    """
    __tablename__ = "evidence_graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("diagnoses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    agent_domain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    metadata_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
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
    diagnosis: Mapped["Diagnosis"] = relationship(
        "Diagnosis",
        back_populates="nodes",
    )
    outgoing_edges: Mapped[List["EvidenceGraphEdge"]] = relationship(
        "EvidenceGraphEdge",
        foreign_keys="EvidenceGraphEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["EvidenceGraphEdge"]] = relationship(
        "EvidenceGraphEdge",
        foreign_keys="EvidenceGraphEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


class EvidenceGraphEdge(Base):
    """
    Directed relation edge between evidence graph nodes.
    """
    __tablename__ = "evidence_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("diagnoses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    diagnosis: Mapped["Diagnosis"] = relationship(
        "Diagnosis",
        back_populates="edges",
    )
    source_node: Mapped["EvidenceGraphNode"] = relationship(
        "EvidenceGraphNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node: Mapped["EvidenceGraphNode"] = relationship(
        "EvidenceGraphNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )
