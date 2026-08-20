"""Window construction for temporal anomaly detection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.ml.anomaly.features import FEATURE_NAMES, extract_features


def row_features(row: Mapping[str, Any]) -> np.ndarray:
    return np.asarray([extract_features(row)[name] for name in FEATURE_NAMES], dtype=np.float32)


def build_windows(
    rows: Sequence[Mapping[str, Any]],
    window_size: int = 30,
    stride: int = 1,
) -> np.ndarray:
    """Create chronological, overlapping windows of telemetry feature vectors."""
    if window_size < 2 or stride < 1:
        raise ValueError("window_size must be >= 2 and stride must be >= 1")
    values = np.asarray([row_features(row) for row in rows], dtype=np.float32)
    if len(values) < window_size:
        return np.empty((0, window_size, len(FEATURE_NAMES)), dtype=np.float32)
    return np.stack(
        [values[start : start + window_size] for start in range(0, len(values) - window_size + 1, stride)]
    )
