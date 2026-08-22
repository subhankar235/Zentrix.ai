"""HypoPG hypothetical index evaluation tool for PostgreSQL.

Provides session-local hypothetical index creation, drops, and planner-cost
evaluations using the PostgreSQL `hypopg` extension.

Results are explicitly labeled as PLANNER_COST_SIGNAL, per PRD.md §5 and
TECHSTACK.md, to clearly distinguish planner estimates from verified runtime
performance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import asyncpg

from app.core.logging import get_logger
from app.tools.pg_introspection import _validate_read_query

logger = get_logger(__name__)

_INDEX_STMT_REGEX = re.compile(
    r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:([A-Za-z_][A-Za-z0-9_$]*)\s+)?ON\s+([A-Za-z_][A-Za-z0-9_$.]*)\s*\((.+)\)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def validate_index_statement(statement: str) -> str:
    """Validate that the candidate SQL is a valid CREATE INDEX statement."""
    cleaned = statement.strip().rstrip(";")
    if not _INDEX_STMT_REGEX.match(cleaned):
        raise ValueError(f"Invalid CREATE INDEX statement: {statement!r}")
    return cleaned


async def check_hypopg_installed(connection: asyncpg.Connection) -> bool:
    """Check if the hypopg extension is installed in the database."""
    try:
        row = await connection.fetchrow(
            "SELECT 1 FROM pg_extension WHERE extname = 'hypopg'"
        )
        return row is not None
    except Exception as exc:
        logger.warning(f"Error checking hypopg extension: {exc}")
        return False


async def create_hypothetical_index(
    connection: asyncpg.Connection,
    index_statement: str,
) -> dict[str, Any]:
    """Create a session-local hypothetical index via hypopg_create_index().

    The index exists only within the current database session and consumes
    no storage on disk.
    """
    valid_stmt = validate_index_statement(index_statement)
    try:
        row = await connection.fetchrow("SELECT * FROM hypopg_create_index($1)", valid_stmt)
        if not row:
            raise RuntimeError(f"hypopg_create_index returned no rows for: {valid_stmt}")
        indexrelid = row[0]
        indexname = row[1] if len(row) > 1 else f"hypo_index_{indexrelid}"
        return {
            "indexrelid": indexrelid,
            "indexname": indexname,
            "statement": valid_stmt,
            "is_hypothetical": True,
            "status": "CREATED",
        }
    except Exception as exc:
        logger.error(f"Failed to create hypothetical index: {exc}")
        raise


async def drop_hypothetical_index(
    connection: asyncpg.Connection,
    indexrelid: int,
) -> bool:
    """Remove a specific hypothetical index by its OID."""
    try:
        row = await connection.fetchrow("SELECT hypopg_drop_index($1)", indexrelid)
        return bool(row[0]) if row else False
    except Exception as exc:
        logger.warning(f"Failed to drop hypothetical index {indexrelid}: {exc}")
        return False


async def reset_hypothetical_indexes(connection: asyncpg.Connection) -> bool:
    """Drop all hypothetical indexes in the current session."""
    try:
        await connection.execute("SELECT hypopg_reset()")
        return True
    except Exception as exc:
        logger.warning(f"Failed to reset hypothetical indexes: {exc}")
        return False


async def list_hypothetical_indexes(
    connection: asyncpg.Connection,
) -> list[dict[str, Any]]:
    """List all active hypothetical indexes in the current session."""
    try:
        rows = await connection.fetch("SELECT * FROM hypopg_list_indexes()")
        return [
            {
                "indexrelid": row["indexrelid"],
                "indexname": row["indexname"],
                "nspname": row.get("nspname"),
                "relname": row.get("relname"),
                "amname": row.get("amname"),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.warning(f"Failed to list hypothetical indexes: {exc}")
        return []


def _extract_plan_cost_and_indexes(plan_payload: Any) -> tuple[float, list[str]]:
    """Extract total estimated cost and index names used from EXPLAIN JSON."""
    root = plan_payload
    if isinstance(plan_payload, list) and plan_payload:
        root = plan_payload[0].get("Plan", plan_payload[0]) if isinstance(plan_payload[0], dict) else plan_payload[0]
    if isinstance(root, dict) and "Plan" in root:
        root = root["Plan"]
    if not isinstance(root, dict):
        return 0.0, []

    total_cost = float(root.get("Total Cost") or root.get("total_cost") or 0.0)
    used_indexes: list[str] = []
    stack = [root]
    while stack:
        node = stack.pop()
        index_name = node.get("Index Name") or node.get("index_name")
        if index_name:
            used_indexes.append(str(index_name))
        stack.extend(node.get("Plans") or [])
    return total_cost, used_indexes


async def evaluate_hypothetical_index(
    connection: asyncpg.Connection,
    query: str,
    index_statement: str,
    *query_args: Any,
) -> dict[str, Any]:
    """Compare baseline planner cost vs. cost with a hypothetical index.

    Cleans up the hypothetical index upon completion and attaches an explicit
    disclaimer stating that planner cost is a theoretical estimate, not a
    proven runtime latency reduction.
    """
    valid_query = _validate_read_query(query)
    valid_index_stmt = validate_index_statement(index_statement)

    # 1. Baseline explain
    baseline_records = await connection.fetch(
        f"EXPLAIN (FORMAT JSON) {valid_query}", *query_args
    )
    baseline_plan = baseline_records[0][0] if baseline_records else {}
    baseline_cost, baseline_indexes = _extract_plan_cost_and_indexes(baseline_plan)

    # 2. Create hypothetical index
    hypo_info = await create_hypothetical_index(connection, valid_index_stmt)
    index_relid = hypo_info["indexrelid"]
    hypo_index_name = hypo_info["indexname"]

    try:
        # 3. Candidate explain with hypothetical index active
        candidate_records = await connection.fetch(
            f"EXPLAIN (FORMAT JSON) {valid_query}", *query_args
        )
        candidate_plan = candidate_records[0][0] if candidate_records else {}
        candidate_cost, candidate_indexes = _extract_plan_cost_and_indexes(candidate_plan)
    finally:
        # 4. Ensure cleanup
        await drop_hypothetical_index(connection, index_relid)

    cost_delta = candidate_cost - baseline_cost
    cost_reduction_ratio = (
        (baseline_cost - candidate_cost) / max(baseline_cost, 1e-6)
        if baseline_cost > 0
        else 0.0
    )
    index_used = (
        hypo_index_name in candidate_indexes
        or any(str(index_relid) in idx for idx in candidate_indexes)
        or (candidate_cost < baseline_cost)
    )

    return {
        "candidate_statement": valid_index_stmt,
        "query": valid_query,
        "baseline_cost": baseline_cost,
        "candidate_cost": candidate_cost,
        "cost_delta": cost_delta,
        "cost_reduction_ratio": max(0.0, min(cost_reduction_ratio, 1.0)),
        "index_used": index_used,
        "is_improvement": bool(cost_reduction_ratio > 0 and index_used),
        "baseline_indexes": baseline_indexes,
        "candidate_indexes": candidate_indexes,
        "signal_type": "PLANNER_COST_SIGNAL",
        "is_verified_performance": False,
        "disclaimer": (
            "Planner cost estimates from HypoPG are theoretical signals only, "
            "not verified runtime performance. Candidate must undergo shadow database "
            "replay and paired statistical verification before deployment."
        ),
    }


async def filter_candidates(
    connection: asyncpg.Connection,
    query: str,
    candidate_statements: Sequence[str],
    *,
    top_k: int = 10,
    min_cost_reduction: float = 0.05,
    query_args: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Fast-filter multiple candidate index statements using HypoPG.

    Reduces large sets of candidate indexes down to the top K viable options
    based on planner cost reduction.
    """
    args = query_args or ()
    results: list[dict[str, Any]] = []

    for statement in candidate_statements:
        try:
            eval_res = await evaluate_hypothetical_index(
                connection, query, statement, *args
            )
            if eval_res["is_improvement"] and eval_res["cost_reduction_ratio"] >= min_cost_reduction:
                results.append(eval_res)
        except Exception as exc:
            logger.warning(
                f"Candidate evaluation failed for {statement!r}: {exc}"
            )

    # Sort descending by cost reduction ratio
    results.sort(key=lambda item: item["cost_reduction_ratio"], reverse=True)
    return results[:top_k]
