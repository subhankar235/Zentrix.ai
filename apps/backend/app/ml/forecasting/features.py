"""Feature 3 L1 Workload & Resource Degradation Forecasting Feature Engineering.

Constructs multi-resolution time-series features (1h–168h lags, rolling window
aggregates, growth rates, acceleration, table/index metrics, and calendar features)
for LightGBM forecasting with conformal calibration.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 3 L1.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import numpy as np

LAG_HOURS = [1, 3, 6, 12, 24, 48, 72, 168]
ROLLING_WINDOWS = [6, 24, 72, 168]

BASE_METRIC_NAMES = [
    "mean_exec_time",
    "max_exec_time",
    "p95_exec_time",
    "calls",
    "rows",
    "shared_blks_read",
    "shared_blks_hit",
    "temp_blks_read",
    "temp_blks_written",
    "cpu_seconds",
    "wal_bytes",
    "dead_tuple_ratio",
    "table_size_bytes",
    "index_size_bytes",
    "idx_scan_ratio",
]


def _feature_names() -> list[str]:
    names: list[str] = []
    # Base snapshot metrics
    names.extend([f"current_{m}" for m in BASE_METRIC_NAMES])
    # Lags
    for lag in LAG_HOURS:
        names.extend([f"lag_{lag}h_{m}" for m in ["mean_exec_time", "p95_exec_time", "calls", "cpu_seconds", "shared_blks_read"]])
    # Rolling aggregates (mean, std, max, growth)
    for window in ROLLING_WINDOWS:
        names.extend([
            f"roll_{window}h_mean_p95",
            f"roll_{window}h_std_p95",
            f"roll_{window}h_max_p95",
            f"roll_{window}h_mean_calls",
            f"roll_{window}h_growth_rate",
        ])
    # Growth & acceleration deltas
    names.extend([
        "growth_1h_p95",
        "growth_24h_p95",
        "growth_168h_p95",
        "acceleration_p95",
        "io_intensity_ratio",
        "cache_hit_ratio",
    ])
    # Calendar features
    names.extend([
        "hour_sin",
        "hour_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "is_weekend",
    ])
    return names


FEATURE_NAMES: list[str] = _feature_names()


def extract_calendar_features(dt: datetime | None) -> dict[str, float]:
    """Extract cyclical calendar features from a timestamp."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    hour = dt.hour + dt.minute / 60.0
    day = dt.weekday() + hour / 24.0

    return {
        "hour_sin": math.sin(2.0 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2.0 * math.pi * hour / 24.0),
        "day_of_week_sin": math.sin(2.0 * math.pi * day / 7.0),
        "day_of_week_cos": math.cos(2.0 * math.pi * day / 7.0),
        "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
    }


def extract_telemetry_features(
    history: Sequence[Mapping[str, Any]],
    current_time: datetime | None = None,
) -> dict[str, float]:
    """Extract full L1 feature vector from a chronological telemetry history sequence.

    `history` should be a sequence of telemetry snapshots sorted in ascending chronological order.
    """
    features: dict[str, float] = {name: 0.0 for name in FEATURE_NAMES}
    if not history:
        calendar = extract_calendar_features(current_time)
        features.update(calendar)
        return features

    latest = history[-1]
    ts_latest = latest.get("timestamp")
    if isinstance(ts_latest, str):
        try:
            ts_latest = datetime.fromisoformat(ts_latest.replace("Z", "+00:00"))
        except Exception:
            ts_latest = current_time or datetime.now(timezone.utc)
    elif not isinstance(ts_latest, datetime):
        ts_latest = current_time or datetime.now(timezone.utc)

    # 1. Base snapshot metrics
    for m in BASE_METRIC_NAMES:
        val = latest.get(m, latest.get(f"avg_{m}", 0.0))
        features[f"current_{m}"] = float(val) if val is not None else 0.0

    # 2. Extract series for lag and rolling features
    p95_series = [float(h.get("p95_exec_time", h.get("max_exec_time", h.get("mean_exec_time", 0.0)))) for h in history]
    calls_series = [float(h.get("calls", 1.0)) for h in history]
    mean_series = [float(h.get("mean_exec_time", 0.0)) for h in history]
    cpu_series = [float(h.get("cpu_seconds", 0.0)) for h in history]
    io_series = [float(h.get("shared_blks_read", 0.0)) for h in history]

    n_points = len(history)

    # 3. Lags
    for lag in LAG_HOURS:
        idx = max(0, n_points - 1 - lag)
        lag_entry = history[idx] if idx < n_points else latest
        features[f"lag_{lag}h_mean_exec_time"] = float(lag_entry.get("mean_exec_time", 0.0))
        features[f"lag_{lag}h_p95_exec_time"] = float(lag_entry.get("p95_exec_time", lag_entry.get("max_exec_time", 0.0)))
        features[f"lag_{lag}h_calls"] = float(lag_entry.get("calls", 0.0))
        features[f"lag_{lag}h_cpu_seconds"] = float(lag_entry.get("cpu_seconds", 0.0))
        features[f"lag_{lag}h_shared_blks_read"] = float(lag_entry.get("shared_blks_read", 0.0))

    # 4. Rolling aggregates
    for window in ROLLING_WINDOWS:
        sub_p95 = p95_series[-window:] if len(p95_series) >= window else p95_series
        sub_calls = calls_series[-window:] if len(calls_series) >= window else calls_series

        mean_val = float(np.mean(sub_p95)) if sub_p95 else 0.0
        std_val = float(np.std(sub_p95)) if len(sub_p95) > 1 else 0.0
        max_val = float(np.max(sub_p95)) if sub_p95 else 0.0
        mean_calls = float(np.mean(sub_calls)) if sub_calls else 0.0

        growth = (sub_p95[-1] - sub_p95[0]) / max(sub_p95[0], 1e-6) if len(sub_p95) >= 2 else 0.0

        features[f"roll_{window}h_mean_p95"] = mean_val
        features[f"roll_{window}h_std_p95"] = std_val
        features[f"roll_{window}h_max_p95"] = max_val
        features[f"roll_{window}h_mean_calls"] = mean_calls
        features[f"roll_{window}h_growth_rate"] = growth

    # 5. Growth deltas and acceleration
    curr_p95 = p95_series[-1] if p95_series else 0.0
    p95_1h = p95_series[-2] if len(p95_series) >= 2 else curr_p95
    p95_24h = p95_series[-25] if len(p95_series) >= 25 else p95_series[0]
    p95_168h = p95_series[-169] if len(p95_series) >= 169 else p95_series[0]

    g1 = (curr_p95 - p95_1h) / max(p95_1h, 1e-6)
    g24 = (curr_p95 - p95_24h) / max(p95_24h, 1e-6)
    g168 = (curr_p95 - p95_168h) / max(p95_168h, 1e-6)

    features["growth_1h_p95"] = g1
    features["growth_24h_p95"] = g24
    features["growth_168h_p95"] = g168
    features["acceleration_p95"] = g1 - (g24 / 24.0)

    # 6. Interaction ratios
    reads = float(latest.get("shared_blks_read", 0.0))
    hits = float(latest.get("shared_blks_hit", 0.0))
    features["cache_hit_ratio"] = hits / max(hits + reads, 1.0)
    features["io_intensity_ratio"] = reads / max(float(latest.get("calls", 1.0)), 1.0)

    # 7. Calendar
    calendar = extract_calendar_features(ts_latest)
    features.update(calendar)

    return features


def build_feature_matrix(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Build numeric feature matrix from extracted feature dictionaries."""
    matrix = np.zeros((len(rows), len(FEATURE_NAMES)), dtype=np.float32)
    for i, row in enumerate(rows):
        for j, name in enumerate(FEATURE_NAMES):
            val = row.get(name, 0.0)
            matrix[i, j] = float(val) if val is not None and not math.isnan(float(val)) else 0.0
    return matrix
