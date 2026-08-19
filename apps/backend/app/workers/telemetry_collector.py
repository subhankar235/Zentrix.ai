"""Continuous read-only telemetry collection from monitored PostgreSQL DBs."""

from __future__ import annotations

import asyncio
import hashlib
import signal
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.customer_db import customer_connection_manager
from app.db.session import async_session_factory
from app.models.connection import DatabaseConnection
from app.models.telemetry import PlanMetric, QueryMetric, TableMetric
from app.tools import pg_introspection

logger = get_logger(__name__)


def _number(value: Any, default: int | float = 0) -> int | float:
    return default if value is None else value


def _int(value: Any) -> int:
    return int(_number(value))


def _float(value: Any) -> float:
    return float(_number(value))


def _plan_hash(features: dict[str, Any]) -> str:
    material = "|".join(
        str(features.get(key, ""))
        for key in ("node_types", "join_types", "estimated_cost", "parallel_workers")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:64]


def _query_hash(query: str | None) -> str:
    return hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:64]


def _is_plan_eligible(query: str | None) -> bool:
    if not query:
        return False
    statement = query.strip().lower()
    return (
        statement.startswith("select")
        or statement.startswith("with")
    ) and ";" not in statement and "$" not in statement


def _rate(current: int | float, previous: int | float | None, elapsed_seconds: float | None) -> float:
    if previous is None or not elapsed_seconds or elapsed_seconds <= 0:
        return 0.0
    return max(0.0, (float(current) - float(previous)) / elapsed_seconds)


def _query_metric(connection_id: UUID, captured_at: datetime, row: dict[str, Any]) -> QueryMetric:
    query_text = row.get("query") or ""
    return QueryMetric(
        id=uuid4(),
        connection_id=connection_id,
        timestamp=captured_at,
        db_id=row.get("db_id"),
        userid=row.get("userid"),
        queryid=row.get("queryid"),
        query_hash=_query_hash(query_text),
        query_text=query_text,
        calls=_int(row.get("calls")),
        total_exec_time=_float(row.get("total_exec_time")),
        mean_exec_time=_float(row.get("mean_exec_time")),
        min_exec_time=_float(row.get("min_exec_time")),
        max_exec_time=_float(row.get("max_exec_time")),
        rows=_int(row.get("rows")),
        shared_blks_hit=_int(row.get("shared_blks_hit")),
        shared_blks_read=_int(row.get("shared_blks_read")),
        shared_blks_dirtied=_int(row.get("shared_blks_dirtied")),
        shared_blks_written=_int(row.get("shared_blks_written")),
        temp_blks_read=_int(row.get("temp_blks_read")),
        temp_blks_written=_int(row.get("temp_blks_written")),
        wal_bytes=_int(row.get("wal_bytes")),
        plans=_int(row.get("plans")),
        planning_time=_float(row.get("planning_time")),
    )


def _table_metric(
    connection_id: UUID,
    captured_at: datetime,
    row: dict[str, Any],
    previous: dict[str, Any] | None,
    elapsed_seconds: float | None,
) -> TableMetric:
    live = _int(row.get("n_live_tup"))
    dead = _int(row.get("n_dead_tup"))
    total_tuples = max(live + dead, 1)
    return TableMetric(
        connection_id=connection_id,
        timestamp=captured_at,
        schema_name=row.get("schemaname") or "public",
        table_name=row.get("relname") or "unknown",
        row_count=live,
        table_size_bytes=_int(row.get("table_size")),
        index_size_bytes=_int(row.get("index_size")),
        seq_scans=_int(row.get("seq_scan")),
        seq_tup_read=_int(row.get("seq_tup_read")),
        idx_scans=_int(row.get("idx_scan")),
        idx_tup_fetch=_int(row.get("idx_tup_fetch")),
        dead_tuples=dead,
        live_tuples=live,
        dead_tuple_ratio=dead / total_tuples,
        insert_rate=_rate(_int(row.get("n_tup_ins")), previous and previous.get("n_tup_ins"), elapsed_seconds),
        update_rate=_rate(_int(row.get("n_tup_upd")), previous and previous.get("n_tup_upd"), elapsed_seconds),
        delete_rate=_rate(_int(row.get("n_tup_del")), previous and previous.get("n_tup_del"), elapsed_seconds),
        last_analyze=row.get("last_analyze"),
        last_autoanalyze=row.get("last_autoanalyze"),
        last_vacuum=row.get("last_vacuum"),
        last_autovacuum=row.get("last_autovacuum"),
    )


async def collect_connection_telemetry(
    connection_id: UUID,
    customer_pool: asyncpg.Pool,
    session: AsyncSession,
    previous_tables: dict[tuple[str, str], dict[str, Any]] | None = None,
    previous_captured_at: datetime | None = None,
    max_plan_queries: int = 10,
) -> dict[str, int]:
    """Collect and persist one snapshot for one monitored database.

    The customer connection is only used through fixed read-only tools. The
    application session receives one atomic batch for this customer.
    """
    captured_at = datetime.now(timezone.utc)
    previous_tables = previous_tables if previous_tables is not None else {}
    elapsed = (captured_at - previous_captured_at).total_seconds() if previous_captured_at else None

    async with customer_pool.acquire() as customer:
        try:
            query_rows = await pg_introspection.get_query_metrics(customer)
        except asyncpg.PostgresError as exc:
            logger.warning("Query telemetry unavailable", extra={"connection_id": str(connection_id), "error": str(exc)})
            query_rows = []
        try:
            table_rows = await pg_introspection.get_table_stats(customer)
        except asyncpg.PostgresError as exc:
            logger.warning("Table telemetry unavailable", extra={"connection_id": str(connection_id), "error": str(exc)})
            table_rows = []

        query_metrics = [_query_metric(connection_id, captured_at, row) for row in query_rows]
        table_metrics = []
        for row in table_rows:
            key = (row.get("schemaname") or "public", row.get("relname") or "unknown")
            table_metrics.append(_table_metric(connection_id, captured_at, row, previous_tables.get(key), elapsed))
            previous_tables[key] = row

        plan_metrics: list[PlanMetric] = []
        for query_metric in query_metrics[:max(0, max_plan_queries)]:
            if not _is_plan_eligible(query_metric.query_text):
                continue
            try:
                features = await pg_introspection.get_query_plan(customer, query_metric.query_text or "")
            except (asyncpg.PostgresError, ValueError) as exc:
                logger.debug(
                    "Skipping plan capture for query",
                    extra={"connection_id": str(connection_id), "query_id": query_metric.queryid, "error": str(exc)},
                )
                continue
            plan_metrics.append(PlanMetric(
                id=uuid4(),
                connection_id=connection_id,
                query_metrics_id=query_metric.id,
                timestamp=captured_at,
                query_id=query_metric.queryid,
                plan_hash=_plan_hash(features),
                node_types=features.get("node_types"),
                estimated_rows=_float(features.get("estimated_rows")),
                actual_rows=_float(features.get("actual_rows")),
                estimated_cost=_float(features.get("estimated_cost")),
                actual_time=_float(features.get("actual_time")),
                buffer_hits=_int(features.get("buffer_hits")),
                buffer_reads=_int(features.get("buffer_reads")),
                join_types=features.get("join_types"),
                parallel_workers=_int(features.get("parallel_workers")),
            ))

    session.add_all([*query_metrics, *table_metrics, *plan_metrics])
    await session.flush()
    return {"queries": len(query_metrics), "tables": len(table_metrics), "plans": len(plan_metrics)}


async def collect_once(
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    connection_manager: Any = customer_connection_manager,
    previous_state: dict[UUID, tuple[datetime, dict[tuple[str, str], dict[str, Any]]]] | None = None,
) -> dict[str, int]:
    """Collect one cycle for every active customer connection."""
    previous_state = previous_state if previous_state is not None else {}
    totals = {"connections": 0, "queries": 0, "tables": 0, "plans": 0, "errors": 0}
    async with session_factory() as session:
        records = (await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.is_active.is_(True))
        )).scalars().all()
        for record in records:
            totals["connections"] += 1
            previous = previous_state.get(record.id)
            try:
                async with session.begin_nested():
                    pool = await connection_manager.get_customer_pool(record.id, db=session)
                    table_state = previous[1] if previous else {}
                    counts = await collect_connection_telemetry(
                        record.id,
                        pool,
                        session,
                        previous_tables=table_state,
                        previous_captured_at=previous[0] if previous else None,
                    )
                captured_at = datetime.now(timezone.utc)
                previous_state[record.id] = (captured_at, table_state)
                for key in ("queries", "tables", "plans"):
                    totals[key] += counts[key]
            except Exception:
                totals["errors"] += 1
                logger.exception("Telemetry collection failed", extra={"connection_id": str(record.id)})
        await session.commit()
    return totals


async def run_worker(
    stop_event: asyncio.Event | None = None,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    connection_manager: Any = customer_connection_manager,
    poll_interval: int | None = None,
) -> None:
    """Run the collector until cancelled or the stop event is set."""
    settings = get_settings()
    interval = max(1, poll_interval or settings.TELEMETRY_POLL_INTERVAL_SECONDS)
    stop_event = stop_event or asyncio.Event()
    previous_state: dict[UUID, tuple[datetime, dict[tuple[str, str], dict[str, Any]]]] = {}
    while not stop_event.is_set():
        await collect_once(session_factory, connection_manager, previous_state)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows event loops and embedded runners may not support this API.
            continue


async def main() -> None:
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    try:
        await run_worker(stop_event=stop_event)
    finally:
        await customer_connection_manager.close_all_pools()


if __name__ == "__main__":
    asyncio.run(main())
