"""
Telemetry SQLAlchemy ORM Models (Query metrics, Table metrics, Plan metrics).
Reference: PRD.md §13 & ARCHITECTURE.md §7
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.connection import DatabaseConnection


class QueryMetric(Base):
    """
    Query-level telemetry snapshot matching pg_stat_statements metrics.
    """
    __tablename__ = "query_metrics"

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
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    db_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    userid: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    queryid: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        index=True,
        nullable=True,
    )
    query_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    query_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    calls: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    total_exec_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    mean_exec_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    min_exec_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    max_exec_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    rows: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    shared_blks_hit: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    shared_blks_read: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    shared_blks_dirtied: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    shared_blks_written: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    temp_blks_read: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    temp_blks_written: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    wal_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    plans: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    planning_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="query_metrics",
    )
    plan_metrics: Mapped[List["PlanMetric"]] = relationship(
        "PlanMetric",
        back_populates="query_metric",
        cascade="all, delete-orphan",
    )


class TableMetric(Base):
    """
    Table-level metrics and statistics from pg_stat_user_tables.
    """
    __tablename__ = "table_metrics"

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
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    schema_name: Mapped[str] = mapped_column(
        String(63),
        default="public",
        nullable=False,
    )
    table_name: Mapped[str] = mapped_column(
        String(63),
        nullable=False,
        index=True,
    )
    row_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    table_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    index_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    seq_scans: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    seq_tup_read: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    idx_scans: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    idx_tup_fetch: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    dead_tuples: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    live_tuples: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    dead_tuple_ratio: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    insert_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    update_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    delete_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    last_analyze: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_autoanalyze: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_vacuum: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_autovacuum: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="table_metrics",
    )


class PlanMetric(Base):
    """
    Execution plan structure and cost estimates from EXPLAIN.
    """
    __tablename__ = "plan_metrics"

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
    query_metrics_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("query_metrics.id", ondelete="SET NULL"),
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
    plan_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    node_types: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    estimated_rows: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    actual_rows: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    estimated_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    actual_time: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    buffer_hits: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    buffer_reads: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    join_types: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    parallel_workers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    raw_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection",
        back_populates="plan_metrics",
    )
    query_metric: Mapped[Optional["QueryMetric"]] = relationship(
        "QueryMetric",
        back_populates="plan_metrics",
    )
