"""Read-only PostgreSQL introspection tools.

This module is the only customer-database boundary used by diagnosis and
forecasting code. Every query is a fixed SELECT/EXPLAIN statement; caller
supplied values are bound parameters and identifiers are validated before
being interpolated.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import asyncpg


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_READ_QUERY = re.compile(r"^(select|with)\b", re.IGNORECASE | re.DOTALL)
_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|merge|alter|create|drop|truncate|grant|revoke|vacuum|analyze|refresh|call|do|copy)\b",
    re.IGNORECASE,
)


def _rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:32]


def _validate_read_query(query: str) -> str:
    statement = query.strip()
    if not statement or ";" in statement:
        raise ValueError("Only one read-only SQL statement is allowed")
    if not _READ_QUERY.match(statement) or _WRITE_KEYWORDS.search(statement):
        raise ValueError("EXPLAIN is restricted to read-only SELECT/WITH queries")
    return statement


def _plan_features(plan: Any) -> dict[str, Any]:
    """Flatten the useful top-level features from EXPLAIN JSON."""
    root = plan
    if isinstance(plan, list) and plan:
        root = plan[0].get("Plan", plan[0]) if isinstance(plan[0], dict) else plan[0]
    if isinstance(root, dict) and "Plan" in root:
        root = root["Plan"]
    if not isinstance(root, dict):
        return {"node_types": [], "join_types": [], "raw_plan": None}

    node_types: list[str] = []
    join_types: list[str] = []
    estimated_rows = 0.0
    actual_rows = 0.0
    buffer_hits = 0
    buffer_reads = 0
    parallel_workers = 0
    stack = [root]
    while stack:
        node = stack.pop()
        node_type = node.get("Node Type")
        if node_type:
            node_types.append(node_type)
        if "Join" in str(node_type):
            join_types.append(node_type)
        estimated_rows += float(node.get("Plan Rows") or 0)
        actual_rows += float(node.get("Actual Rows") or 0)
        buffer_hits += int(node.get("Shared Hit Blocks") or 0)
        buffer_reads += int(node.get("Shared Read Blocks") or 0)
        parallel_workers = max(parallel_workers, int(node.get("Workers Launched") or 0))
        stack.extend(node.get("Plans") or [])

    return {
        "node_types": node_types,
        "join_types": join_types,
        "estimated_rows": estimated_rows,
        "actual_rows": actual_rows,
        "estimated_cost": float(root.get("Total Cost") or 0),
        "actual_time": float(root.get("Actual Total Time") or 0),
        "buffer_hits": buffer_hits,
        "buffer_reads": buffer_reads,
        "parallel_workers": parallel_workers,
    }


async def get_explain_plan(connection: asyncpg.Connection, query: str, *args: Any) -> dict[str, Any]:
    statement = _validate_read_query(query)
    async with connection.transaction(readonly=True):
        records = await connection.fetch(
            "EXPLAIN (ANALYZE, BUFFERS, WAL, SETTINGS, FORMAT JSON) " + statement,
            *args,
        )
    payload = records[0][0] if records else None
    features = _plan_features(payload)
    features["query_hash"] = _query_hash(query)
    return features


async def get_plan_history(connection: asyncpg.Connection, connection_id: Any, query_id: int, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT captured_at, query_id, plan_hash, node_types, estimated_rows,
               actual_rows, estimated_cost, actual_time, buffer_hits,
               buffer_reads, join_types, parallel_workers
        FROM plan_metrics
        WHERE connection_id = $1 AND query_id = $2
        ORDER BY captured_at DESC LIMIT $3
    """, connection_id, query_id, limit))


async def get_pg_stats(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if schema is not None:
        args.append(schema); clauses.append(f"schemaname = ${len(args)}")
    if table is not None:
        args.append(table); clauses.append(f"tablename = ${len(args)}")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return _rows(await connection.fetch(
        "SELECT schemaname, tablename, attname, null_frac, n_distinct, most_common_vals, "
        "most_common_freqs, histogram_bounds, correlation FROM pg_stats" + where,
        *args,
    ))


async def get_query_metrics(connection: asyncpg.Connection, limit: int = 500) -> list[dict[str, Any]]:
    """Return normalized query statistics from the current customer database."""
    return _rows(await connection.fetch("""
        SELECT d.oid AS db_id, s.userid, s.queryid, s.query,
               s.calls, s.total_exec_time, s.mean_exec_time,
               s.min_exec_time, s.max_exec_time, s.rows,
               s.shared_blks_hit, s.shared_blks_read,
               s.shared_blks_dirtied, s.shared_blks_written,
               s.temp_blks_read, s.temp_blks_written,
               COALESCE(s.wal_bytes, 0) AS wal_bytes,
               COALESCE(s.plans, 0) AS plans,
               COALESCE(s.total_plan_time, 0) AS planning_time
        FROM pg_stat_statements s
        LEFT JOIN pg_database d ON d.oid = s.dbid
        WHERE s.query IS NOT NULL
          AND s.query NOT ILIKE '%pg_stat_statements%'
        ORDER BY s.total_exec_time DESC
        LIMIT $1
    """, max(1, min(limit, 5000))))


async def get_table_statistics(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    return await get_table_stats(connection, schema=schema, table=table)


def compare_plan(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    previous_hash = previous.get("plan_hash")
    current_hash = current.get("plan_hash")
    return {
        "plan_changed": previous_hash != current_hash,
        "previous_plan_hash": previous_hash,
        "current_plan_hash": current_hash,
        "estimated_rows_delta": (current.get("estimated_rows") or 0) - (previous.get("estimated_rows") or 0),
        "actual_rows_delta": (current.get("actual_rows") or 0) - (previous.get("actual_rows") or 0),
        "actual_time_delta": (current.get("actual_time") or 0) - (previous.get("actual_time") or 0),
    }


def calculate_cardinality_error(estimated_rows: float | None, actual_rows: float | None) -> float:
    estimated = max(float(estimated_rows or 0), 0.0)
    actual = max(float(actual_rows or 0), 0.0)
    return math.log1p(actual) - math.log1p(estimated)


async def get_pg_activity(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT pid, datname, usename, application_name, client_addr, state,
               wait_event_type, wait_event, query_start, xact_start,
               backend_xid, backend_xmin, query
        FROM pg_stat_activity
        WHERE pid <> pg_backend_pid()
        ORDER BY query_start NULLS LAST
    """))


async def get_pg_locks(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT l.pid, l.locktype, l.mode, l.granted, l.relation,
               l.transactionid, a.query, a.state, a.query_start
        FROM pg_locks l
        LEFT JOIN pg_stat_activity a ON a.pid = l.pid
        ORDER BY l.granted, l.pid
    """))


async def get_wait_events(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT pid, wait_event_type, wait_event, state, query_start, query
        FROM pg_stat_activity
        WHERE wait_event IS NOT NULL
        ORDER BY query_start NULLS LAST
    """))


def build_lock_graph(locks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    holders = defaultdict(list)
    for lock in locks:
        if lock.get("granted") and lock.get("relation") is not None:
            holders[lock["relation"]].append(lock.get("pid"))
    edges = []
    for lock in locks:
        if lock.get("granted") or lock.get("relation") is None:
            continue
        for holder in holders[lock["relation"]]:
            edges.append({"blocking_pid": holder, "blocked_pid": lock.get("pid"), "relation": lock["relation"], "mode": lock.get("mode")})
    return edges


async def get_table_stats(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if schema is not None:
        args.append(schema); clauses.append(f"schemaname = ${len(args)}")
    if table is not None:
        args.append(table); clauses.append(f"relname = ${len(args)}")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return _rows(await connection.fetch("""
        SELECT schemaname, relname, n_live_tup, n_dead_tup, seq_scan,
               seq_tup_read, idx_scan, idx_tup_fetch, n_tup_ins, n_tup_upd,
               n_tup_del, last_analyze, last_autoanalyze, last_vacuum,
               last_autovacuum, pg_total_relation_size(relid) AS table_size,
               pg_indexes_size(relid) AS index_size
        FROM pg_stat_user_tables
    """ + where, *args))


async def get_vacuum_progress(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT pid, datname, relid, phase, heap_blks_total, heap_blks_scanned,
               heap_blks_vacuumed, index_vacuum_count, max_dead_tuples,
               num_dead_tuples FROM pg_stat_progress_vacuum
    """))


async def get_autovacuum_history(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    return await get_table_stats(connection, schema=schema, table=table)


async def estimate_bloat(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    rows = await get_table_stats(connection, schema=schema, table=table)
    return [{**row, "dead_tuple_ratio": (row.get("n_dead_tup") or 0) / max((row.get("n_live_tup") or 0) + (row.get("n_dead_tup") or 0), 1)} for row in rows]


async def get_dead_tuple_ratio(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    return await estimate_bloat(connection, schema=schema, table=table)


async def get_buffer_stats(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT schemaname, relname, heap_blks_read, heap_blks_hit,
               idx_blks_read, idx_blks_hit, toast_blks_read, toast_blks_hit
        FROM pg_statio_user_tables
    """))


async def get_io_stats(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT schemaname, relname, heap_blks_read, heap_blks_hit,
               idx_blks_read, idx_blks_hit, toast_blks_read, toast_blks_hit
        FROM pg_statio_user_tables
        UNION ALL
        SELECT schemaname, relname, idx_blks_read, idx_blks_hit,
               NULL, NULL, NULL, NULL FROM pg_statio_user_indexes
    """))


async def get_explain_buffers(connection: asyncpg.Connection, query: str, *args: Any) -> dict[str, Any]:
    result = await get_explain_plan(connection, query, *args)
    return {key: result.get(key) for key in ("buffer_hits", "buffer_reads", "actual_time", "node_types")}


async def get_temp_file_stats(connection: asyncpg.Connection) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT datname, temp_files, temp_bytes FROM pg_stat_database ORDER BY datname
    """))


async def get_wal_stats(connection: asyncpg.Connection) -> dict[str, Any]:
    row = await connection.fetchrow("SELECT * FROM pg_stat_wal")
    return dict(row) if row else {}


async def get_indexes(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if schema is not None:
        args.append(schema); clauses.append(f"schemaname = ${len(args)}")
    if table is not None:
        args.append(table); clauses.append(f"tablename = ${len(args)}")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return _rows(await connection.fetch("SELECT schemaname, tablename, indexname, tablespace, indexdef FROM pg_indexes" + where, *args))


async def get_index_usage(connection: asyncpg.Connection, schema: str | None = None, table: str | None = None) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if schema is not None:
        args.append(schema); clauses.append(f"s.schemaname = ${len(args)}")
    if table is not None:
        args.append(table); clauses.append(f"s.relname = ${len(args)}")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return _rows(await connection.fetch("""
        SELECT s.schemaname, s.relname, s.indexrelname, s.idx_scan,
               s.idx_tup_read, s.idx_tup_fetch, i.indexrelid
        FROM pg_stat_user_indexes s
        JOIN pg_index i ON i.indexrelid = s.indexrelid
    """ + where, *args))


async def get_table_schema(connection: asyncpg.Connection, schema: str, table: str) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT table_schema, table_name, column_name, ordinal_position,
               data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
    """, schema, table))


async def get_constraints(connection: asyncpg.Connection, schema: str, table: str) -> list[dict[str, Any]]:
    return _rows(await connection.fetch("""
        SELECT tc.constraint_name, tc.constraint_type, kcu.column_name,
               ccu.table_schema AS foreign_table_schema,
               ccu.table_name AS foreign_table_name,
               ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        LEFT JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.table_schema = $1 AND tc.table_name = $2
        ORDER BY tc.constraint_name
    """, schema, table))


async def get_query_plan(connection: asyncpg.Connection, query: str, *args: Any) -> dict[str, Any]:
    return await get_explain_plan(connection, query, *args)
