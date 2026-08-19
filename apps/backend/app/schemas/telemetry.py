"""
Telemetry Pydantic Schemas (Query, Table, and Plan Metrics).
Reference: PRD.md §13 & ARCHITECTURE.md §4
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QueryMetricBase(BaseModel):
    timestamp: datetime
    query_hash: str
    query_text: Optional[str] = None
    queryid: Optional[int] = None
    db_id: Optional[int] = None
    userid: Optional[int] = None
    calls: int = 0
    total_exec_time: float = 0.0
    mean_exec_time: float = 0.0
    min_exec_time: float = 0.0
    max_exec_time: float = 0.0
    rows: int = 0
    shared_blks_hit: int = 0
    shared_blks_read: int = 0
    shared_blks_dirtied: int = 0
    shared_blks_written: int = 0
    temp_blks_read: int = 0
    temp_blks_written: int = 0
    wal_bytes: int = 0
    plans: int = 0
    planning_time: float = 0.0


class QueryMetricCreate(QueryMetricBase):
    connection_id: uuid.UUID


class QueryMetricOut(QueryMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    created_at: datetime


class TableMetricBase(BaseModel):
    timestamp: datetime
    schema_name: str = "public"
    table_name: str
    row_count: int = 0
    table_size_bytes: int = 0
    index_size_bytes: int = 0
    seq_scans: int = 0
    seq_tup_read: int = 0
    idx_scans: int = 0
    idx_tup_fetch: int = 0
    dead_tuples: int = 0
    live_tuples: int = 0
    dead_tuple_ratio: float = 0.0
    insert_rate: float = 0.0
    update_rate: float = 0.0
    delete_rate: float = 0.0
    last_analyze: Optional[datetime] = None
    last_autoanalyze: Optional[datetime] = None
    last_vacuum: Optional[datetime] = None
    last_autovacuum: Optional[datetime] = None


class TableMetricCreate(TableMetricBase):
    connection_id: uuid.UUID


class TableMetricOut(TableMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    created_at: datetime


class PlanMetricBase(BaseModel):
    timestamp: datetime
    plan_hash: str
    query_id: Optional[int] = None
    node_types: Optional[List[str]] = None
    estimated_rows: float = 0.0
    actual_rows: float = 0.0
    estimated_cost: float = 0.0
    actual_time: float = 0.0
    buffer_hits: int = 0
    buffer_reads: int = 0
    join_types: Optional[List[str]] = None
    parallel_workers: int = 0
    raw_plan: Optional[Dict[str, Any]] = None


class PlanMetricCreate(PlanMetricBase):
    connection_id: uuid.UUID
    query_metrics_id: Optional[uuid.UUID] = None


class PlanMetricOut(PlanMetricBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    query_metrics_id: Optional[uuid.UUID] = None
    created_at: datetime


class TelemetrySummaryResponse(BaseModel):
    connection_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    total_queries: int
    avg_latency_ms: float
    p95_latency_ms: float
    cache_hit_ratio: float
    active_tables_count: int
    top_queries: List[QueryMetricOut] = Field(default_factory=list)
    top_bloated_tables: List[TableMetricOut] = Field(default_factory=list)
