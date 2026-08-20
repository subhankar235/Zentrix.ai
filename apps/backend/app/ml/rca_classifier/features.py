"""Feature and label contracts for the root-cause classifier."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


CAUSES = (
    "STALE_STATISTICS",
    "PLAN_FLIP",
    "CARDINALITY_MISESTIMATION",
    "LOCK_CONTENTION",
    "INDEX_MISSING",
    "INDEX_UNUSED",
    "VACUUM_LAG",
    "BLOAT",
    "BUFFER_PRESSURE",
    "IO_SATURATION",
    "TEMP_SPILL",
    "CONNECTION_CONTENTION",
    "CHECKPOINT_PRESSURE",
    "UNKNOWN",
)

FEATURE_NAMES = (
    "cardinality_error",
    "plan_flip",
    "estimated_cost",
    "actual_time",
    "buffer_hit_ratio",
    "buffer_reads",
    "lock_wait_seconds",
    "dead_tuple_ratio",
    "vacuum_age",
    "analyze_age",
    "table_growth_rate",
    "idx_scan_ratio",
    "temp_io",
    "wal_rate",
    "connection_count",
    "latency_p95",
)


def _number(row: Mapping[str, Any], *names: str) -> float:
    for name in names:
        value = row.get(name)
        if value is not None:
            return float(value)
    return 0.0


def extract_features(row: Mapping[str, Any]) -> dict[str, float]:
    hits = _number(row, "buffer_hits", "shared_blks_hit")
    reads = _number(row, "buffer_reads", "shared_blks_read")
    scans = _number(row, "idx_scans", "idx_scan")
    seq_scans = _number(row, "seq_scans", "seq_scan")
    return {
        "cardinality_error": _number(row, "cardinality_error"),
        "plan_flip": _number(row, "plan_flip", "plan_changed"),
        "estimated_cost": _number(row, "estimated_cost"),
        "actual_time": _number(row, "actual_time", "execution_time", "mean_exec_time"),
        "buffer_hit_ratio": _number(row, "buffer_hit_ratio") or hits / max(hits + reads, 1.0),
        "buffer_reads": reads,
        "lock_wait_seconds": _number(row, "lock_wait_seconds", "lock_wait"),
        "dead_tuple_ratio": _number(row, "dead_tuple_ratio"),
        "vacuum_age": _number(row, "vacuum_age"),
        "analyze_age": _number(row, "analyze_age"),
        "table_growth_rate": _number(row, "table_growth_rate", "table_size_bytes_growth_rate"),
        "idx_scan_ratio": _number(row, "idx_scan_ratio") or scans / max(scans + seq_scans, 1.0),
        "temp_io": _number(row, "temp_io") + _number(row, "temp_blks_read", "temp_blks_written"),
        "wal_rate": _number(row, "wal_rate", "wal_bytes"),
        "connection_count": _number(row, "connection_count", "connections"),
        "latency_p95": _number(row, "latency_p95", "p95_latency", "max_exec_time"),
    }


def build_feature_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray(
        [[extract_features(row)[name] for name in FEATURE_NAMES] for row in rows],
        dtype=np.float32,
    )


def build_label_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    matrix = np.zeros((len(rows), len(CAUSES)), dtype=np.int32)
    for row_index, row in enumerate(rows):
        labels = row.get("labels", row.get("causes", []))
        if isinstance(labels, str):
            labels = [labels]
        for label in labels:
            if label in CAUSES:
                matrix[row_index, CAUSES.index(label)] = 1
    return matrix
