"""Inference for the promoted Isolation Forest anomaly model."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.ml.anomaly.features import build_feature_matrix, extract_features, robust_z_scores


def _load(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    model_path = path or os.getenv("ANOMALY_MODEL_PATH", "anomaly_model.joblib")
    return joblib.load(Path(model_path))


def predict(
    features: Mapping[str, Any],
    model_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    artifact = _load(model_path)
    values = build_feature_matrix([features])
    model = artifact["model"]
    raw_score = float(model.decision_function(values)[0])
    # Isolation Forest's decision score is positive for normal observations.
    anomaly_score = 1.0 / (1.0 + math.exp(8.0 * raw_score))
    z_scores = robust_z_scores(values, artifact["median"], artifact["mad"])[0]
    return {
        "anomaly_score": float(np.clip(anomaly_score, 0.0, 1.0)),
        "is_anomaly": bool(model.predict(values)[0] == -1),
        "raw_score": raw_score,
        "robust_z_scores": dict(zip(extract_features(features), z_scores.tolist())),
    }
