"""Feature and target contracts for the Feature 2 outcome model.

Rows may come from ``OptimizationExperiment`` records or from the
optimization laboratory.  The adapter intentionally accepts both flat rows
and ``baseline``/``candidate`` mappings so training and online scoring share
exactly the same transformations.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


TARGET_NAMES = (
    "delta_latency",
    "delta_p95",
    "delta_cpu",
    "delta_io",
    "delta_buffer_reads",
)

FEATURE_NAMES = (
    "baseline_latency",
    "baseline_p95",
    "baseline_cpu",
    "baseline_io",
    "baseline_buffer_reads",
    "baseline_buffer_hits",
    "baseline_rows",
    "baseline_calls",
    "baseline_selectivity",
    "table_size_bytes",
    "index_size_bytes",
    "dead_tuple_ratio",
    "idx_scan_ratio",
    "cardinality_error",
    "plan_cost",
    "plan_actual_time",
    "plan_buffer_reads",
    "query_frequency",
    "candidate_is_create_index",
    "candidate_is_drop_index",
    "candidate_is_analyze",
    "candidate_is_rewrite",
    "candidate_is_config",
    "candidate_sql_length",
    "candidate_has_where",
    "candidate_has_join",
    "candidate_column_count",
    "candidate_is_partial",
    "candidate_selectivity",
    "candidate_stats_target",
)

OUTCOME_LABELS = ("GOOD", "BAD", "NEUTRAL", "REGRESSION")
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _mapping(row: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = row.get(name)
    return value if isinstance(value, Mapping) else row


def _number(row: Mapping[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _baseline(row: Mapping[str, Any], name: str, *aliases: str) -> float:
    source = _mapping(row, "baseline")
    return _number(source, name, *aliases, f"baseline_{name}")


def _candidate(row: Mapping[str, Any], name: str, *aliases: str) -> float:
    source = _mapping(row, "candidate")
    return _number(source, name, *aliases, f"candidate_{name}")


def extract_features(row: Mapping[str, Any]) -> dict[str, float]:
    """Normalize one experiment/lab row into the stable numeric feature vector."""
    candidate = _mapping(row, "candidate")
    sql = str(row.get("candidate_sql", row.get("sql", candidate.get("candidate_sql", candidate.get("sql", "")))) or "")
    strategy = str(row.get("strategy", row.get("candidate_type", candidate.get("strategy", candidate.get("type", "")))) or "").upper()
    table_size = _number(row, "table_size_bytes", "table_size", "table_size_mb")
    if "table_size_mb" in row and "table_size_bytes" not in row:
        table_size *= 1024 * 1024
    baseline_latency = _baseline(row, "latency", "mean_latency", "execution_time")
    baseline_p95 = _baseline(row, "p95", "latency_p95", "p95_latency")
    baseline_cpu = _baseline(row, "cpu", "cpu_time")
    baseline_io = _baseline(row, "io", "io_bytes", "read_bytes")
    baseline_buffer_reads = _baseline(row, "buffer_reads", "shared_blks_read")
    baseline_buffer_hits = _baseline(row, "buffer_hits", "shared_blks_hit")
    return {
        "baseline_latency": baseline_latency,
        "baseline_p95": baseline_p95,
        "baseline_cpu": baseline_cpu,
        "baseline_io": baseline_io,
        "baseline_buffer_reads": baseline_buffer_reads,
        "baseline_buffer_hits": baseline_buffer_hits,
        "baseline_rows": _baseline(row, "rows", "actual_rows"),
        "baseline_calls": _baseline(row, "calls", "query_calls"),
        "baseline_selectivity": _number(row, "baseline_selectivity", "selectivity"),
        "table_size_bytes": table_size,
        "index_size_bytes": _number(row, "index_size_bytes", "index_size"),
        "dead_tuple_ratio": _number(row, "dead_tuple_ratio"),
        "idx_scan_ratio": _number(row, "idx_scan_ratio"),
        "cardinality_error": _number(row, "cardinality_error"),
        "plan_cost": _number(row, "plan_cost", "estimated_cost"),
        "plan_actual_time": _number(row, "plan_actual_time", "actual_time"),
        "plan_buffer_reads": _number(row, "plan_buffer_reads", "buffer_reads"),
        "query_frequency": _number(row, "query_frequency", "qps", "frequency"),
        "candidate_is_create_index": float(strategy in {"CREATE_INDEX", "CREATE INDEX"} or "CREATE INDEX" in sql.upper()),
        "candidate_is_drop_index": float(strategy in {"DROP_INDEX", "DROP INDEX"} or "DROP INDEX" in sql.upper()),
        "candidate_is_analyze": float(strategy == "ANALYZE" or re.search(r"\bANALYZE\b", sql, re.I) is not None),
        "candidate_is_rewrite": float(strategy in {"REWRITE", "QUERY_REWRITE"}),
        "candidate_is_config": float(strategy in {"CONFIG", "CONFIGURATION"}),
        "candidate_sql_length": float(len(sql)),
        "candidate_has_where": float(re.search(r"\bWHERE\b", sql, re.I) is not None),
        "candidate_has_join": float(re.search(r"\bJOIN\b", sql, re.I) is not None),
        "candidate_column_count": float(len(re.findall(r"[,()]", sql)) + 1 if sql else 0),
        "candidate_is_partial": float("WHERE" in sql.upper() and strategy in {"CREATE_INDEX", "CREATE INDEX"}),
        "candidate_selectivity": _number(row, "candidate_selectivity", "index_selectivity"),
        "candidate_stats_target": _number(row, "candidate_stats_target", "statistics_target"),
    }


def build_feature_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray([[extract_features(row)[name] for name in FEATURE_NAMES] for row in rows], dtype=np.float32)


def _target_value(row: Mapping[str, Any], target: str) -> float:
    explicit = row.get(target)
    if explicit is None:
        explicit = row.get({
            "delta_latency": "actual_latency_delta",
            "delta_p95": "actual_p95_delta",
            "delta_cpu": "actual_cpu_delta",
            "delta_io": "actual_io_delta",
            "delta_buffer_reads": "actual_buffer_reads_delta",
        }[target])
    if explicit is not None:
        return float(explicit)
    metric = target.removeprefix("delta_")
    return _candidate(row, metric, f"candidate_{metric}") - _baseline(row, metric, f"baseline_{metric}")


def build_target_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray([[_target_value(row, target) for target in TARGET_NAMES] for row in rows], dtype=np.float32)


def outcome_label(row: Mapping[str, Any], deltas: Mapping[str, float] | None = None) -> str:
    explicit = str(row.get("outcome_label", row.get("label", row.get("outcome", ""))) or "").upper()
    if explicit in OUTCOME_LABELS:
        return explicit
    values = deltas or {target: _target_value(row, target) for target in TARGET_NAMES}
    baseline = abs(_baseline(row, "latency", "mean_latency", "execution_time"))
    latency_delta = float(values.get("delta_latency", 0.0))
    threshold = max(baseline * 0.05, 1e-6)
    if latency_delta < -threshold:
        return "GOOD"
    if latency_delta > threshold * 2:
        return "REGRESSION"
    if latency_delta > threshold:
        return "BAD"
    return "NEUTRAL"
