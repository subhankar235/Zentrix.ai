"""Feature extraction for multivariate PostgreSQL anomaly detection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


FEATURE_NAMES = (
    "latency_p50",
    "latency_p95",
    "execution_time",
    "planning_time",
    "buffer_hits",
    "buffer_reads",
    "temp_blks_read",
    "temp_blks_written",
    "lock_wait_seconds",
    "dead_tuple_ratio",
    "cache_hit_ratio",
    "wal_rate",
    "table_growth_rate",
    "vacuum_age",
    "analyze_age",
    "cardinality_error",
    "plan_flip",
)


def _value(row: Mapping[str, Any], name: str) -> float:
    aliases = {
        "latency_p50": ("latency_p50", "p50_latency", "mean_exec_time"),
        "latency_p95": ("latency_p95", "p95_latency", "max_exec_time"),
        "execution_time": ("execution_time", "actual_time", "total_exec_time"),
        "planning_time": ("planning_time", "plan_time"),
        "buffer_hits": ("buffer_hits", "shared_blks_hit"),
        "buffer_reads": ("buffer_reads", "shared_blks_read"),
        "temp_blks_read": ("temp_blks_read", "temp_blocks_read"),
        "temp_blks_written": ("temp_blks_written", "temp_blocks_written"),
        "lock_wait_seconds": ("lock_wait_seconds", "lock_wait", "wait_seconds"),
        "dead_tuple_ratio": ("dead_tuple_ratio",),
        "cache_hit_ratio": ("cache_hit_ratio",),
        "wal_rate": ("wal_rate", "wal_bytes"),
        "table_growth_rate": ("table_growth_rate", "table_size_bytes_growth_rate"),
        "vacuum_age": ("vacuum_age",),
        "analyze_age": ("analyze_age",),
        "cardinality_error": ("cardinality_error",),
        "plan_flip": ("plan_flip", "plan_changed"),
    }
    for key in aliases[name]:
        value = row.get(key)
        if value is not None:
            return float(value)
    return 0.0


def extract_features(row: Mapping[str, Any]) -> dict[str, float]:
    """Normalize one telemetry row into the stable 17-feature contract."""
    return {name: _value(row, name) for name in FEATURE_NAMES}


def build_feature_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray(
        [[features[name] for name in FEATURE_NAMES] for features in map(extract_features, rows)],
        dtype=np.float32,
    )


def robust_z_scores(
    values: np.ndarray,
    median: np.ndarray | None = None,
    mad: np.ndarray | None = None,
) -> np.ndarray:
    """Calculate interpretable robust z-scores using median absolute deviation."""
    median = np.median(values, axis=0) if median is None else median
    mad = np.median(np.abs(values - median), axis=0) if mad is None else mad
    scale = np.where(mad > 1e-12, 1.4826 * mad, 1.0)
    return (values - median) / scale
