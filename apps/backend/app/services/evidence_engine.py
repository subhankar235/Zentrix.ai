"""Deterministic computations over PostgreSQL telemetry.

This module deliberately has no database, model, or agent dependencies.  The
functions accept mappings so they can operate on rows returned by asyncpg as
well as normalized telemetry records loaded from the application database.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


def _number(row: Mapping[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = row.get(name)
        if value is not None:
            return float(value)
    return default


def calculate_cardinality_error(
    estimated_rows: float | None, actual_rows: float | None
) -> float:
    """Return signed log cardinality error, positive when estimates are low."""
    estimated = max(float(estimated_rows or 0), 0.0)
    actual = max(float(actual_rows or 0), 0.0)
    return math.log1p(actual) - math.log1p(estimated)


def diff_plans(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two executions of the same query and identify a plan flip."""
    previous_hash = previous.get("plan_hash")
    current_hash = current.get("plan_hash")
    plan_changed = previous_hash != current_hash
    return {
        "plan_changed": plan_changed,
        "plan_flip": plan_changed,
        "previous_plan_hash": previous_hash,
        "current_plan_hash": current_hash,
        "estimated_rows_delta": _number(current, "estimated_rows")
        - _number(previous, "estimated_rows"),
        "actual_rows_delta": _number(current, "actual_rows")
        - _number(previous, "actual_rows"),
        "actual_time_delta": _number(current, "actual_time")
        - _number(previous, "actual_time"),
        "previous_cardinality_error": calculate_cardinality_error(
            previous.get("estimated_rows"), previous.get("actual_rows")
        ),
        "current_cardinality_error": calculate_cardinality_error(
            current.get("estimated_rows"), current.get("actual_rows")
        ),
    }


def detect_plan_flip(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """Return whether two plan snapshots have different non-null fingerprints."""
    return bool(diff_plans(previous, current)["plan_flip"])


def build_lock_graph(
    locks: Sequence[Mapping[str, Any]],
    activity: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build blocking edges from granted and waiting PostgreSQL locks.

    PostgreSQL's lock view does not always include a ``blocking_pid`` column;
    the relation/resource and granted state are sufficient to derive edges.
    Explicit blocking PIDs, when present in introspection output, are honored.
    Duplicate edges are removed while preserving input order.
    """
    del activity  # Activity is useful context, but lock compatibility is explicit here.
    holders: dict[Any, list[Any]] = defaultdict(list)
    for lock in locks:
        if lock.get("granted") and lock.get("relation") is not None:
            holders[lock["relation"]].append(lock.get("pid"))

    edges: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any, Any]] = set()
    for lock in locks:
        if lock.get("granted") or lock.get("relation") is None:
            continue
        relation = lock["relation"]
        blocking_pids = (
            [lock["blocking_pid"]]
            if lock.get("blocking_pid") is not None
            else holders.get(relation, [])
        )
        for blocking_pid in blocking_pids:
            key = (blocking_pid, lock.get("pid"), relation, lock.get("mode"))
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "blocking_pid": blocking_pid,
                    "blocked_pid": lock.get("pid"),
                    "relation": relation,
                    "mode": lock.get("mode"),
                }
            )
    return edges


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _age_seconds(now: datetime, value: Any) -> float | None:
    timestamp = _as_datetime(value)
    if timestamp is None:
        return None
    return max(0.0, (now - timestamp).total_seconds())


def calculate_vacuum_metrics(
    row: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculate bloat, maintenance age, lag, and growth metrics for one row.

    Ages and rates are expressed in seconds and units per second respectively.
    Missing maintenance timestamps or an unavailable prior sample produce
    ``None`` rather than an invented value.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    live = max(_number(row, "live_tuples", "n_live_tup"), 0.0)
    dead = max(_number(row, "dead_tuples", "n_dead_tup"), 0.0)
    total = live + dead
    result = dict(row)
    result["dead_tuple_ratio"] = dead / total if total else 0.0
    vacuum_ages = [
        age for age in (
            _age_seconds(now, row.get("last_autovacuum")),
            _age_seconds(now, row.get("last_vacuum")),
        ) if age is not None
    ]
    analyze_ages = [
        age for age in (
            _age_seconds(now, row.get("last_autoanalyze")),
            _age_seconds(now, row.get("last_analyze")),
        ) if age is not None
    ]
    result["vacuum_age"] = min(vacuum_ages) if vacuum_ages else None
    result["analyze_age"] = min(analyze_ages) if analyze_ages else None
    result["autovacuum_lag"] = _age_seconds(now, row.get("last_autovacuum"))

    elapsed = None
    if previous is not None:
        current_time = _as_datetime(row.get("timestamp") or row.get("captured_at"))
        previous_time = _as_datetime(previous.get("timestamp") or previous.get("captured_at"))
        if current_time and previous_time:
            elapsed = (current_time - previous_time).total_seconds()
    if elapsed is None or elapsed <= 0 or previous is None:
        for key in ("table_size_bytes", "index_size_bytes", "row_count"):
            result[f"{key}_growth_rate"] = None
        result["table_growth_rate"] = None
        result["index_growth_rate"] = None
        result["row_growth_rate"] = None
    else:
        values = (
            ("table_size_bytes", ("table_size_bytes", "table_size"), "table_growth_rate"),
            ("index_size_bytes", ("index_size_bytes", "index_size"), "index_growth_rate"),
            ("row_count", ("row_count", "live_tuples", "n_live_tup"), "row_growth_rate"),
        )
        for output_key, keys, alias in values:
            current_value = _number(row, *keys)
            previous_value = _number(previous, *keys)
            rate = (current_value - previous_value) / elapsed
            result[f"{output_key}_growth_rate"] = rate
            result[alias] = rate
    return result


def compute_vacuum_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Compute vacuum metrics for chronologically ordered table snapshots."""
    previous_by_table: dict[tuple[Any, Any], Mapping[str, Any]] = {}
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("schema_name", row.get("schemaname")), row.get("table_name", row.get("relname")))
        metrics = calculate_vacuum_metrics(row, previous_by_table.get(key), now=now)
        result.append(metrics)
        previous_by_table[key] = row
    return result
