"""Inference for the Feature 2 query-performance delta predictor."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.ml.delta_predictor.features import TARGET_NAMES, build_feature_matrix, outcome_label


def _load(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return joblib.load(Path(path or os.getenv("DELTA_MODEL_PATH", "delta_predictor.joblib")))


def predict(row: Mapping[str, Any], model_path: str | os.PathLike[str] | None = None, *, z_value: float = 1.96) -> dict[str, Any]:
    """Return all target deltas with bootstrap uncertainty intervals."""
    if z_value <= 0:
        raise ValueError("z_value must be positive")
    artifact = _load(model_path)
    values = build_feature_matrix([row])
    estimates: dict[str, float] = {}
    intervals: dict[str, dict[str, float]] = {}
    target_confidence: dict[str, float] = {}
    residual_scales = np.asarray(artifact.get("residual_scales", np.zeros(len(TARGET_NAMES))), dtype=float)
    for index, target in enumerate(artifact.get("target_names", TARGET_NAMES)):
        members = np.asarray([float(model.predict(values)[0]) for model in artifact["models"][index]], dtype=float)
        estimate = float(np.mean(members))
        ensemble_variance = np.var(members, ddof=1) if len(members) > 1 else 0.0
        uncertainty = float(np.sqrt(ensemble_variance + residual_scales[index] ** 2))
        # A lower/upper interval is conservative: it includes model spread and
        # the observed training residual scale.
        half_width = z_value * uncertainty
        lower, upper = estimate - half_width, estimate + half_width
        confidence = float(np.clip(1.0 / (1.0 + half_width / max(abs(estimate), residual_scales[index], 1e-6)), 0.0, 1.0))
        estimates[target] = estimate
        intervals[target] = {"estimate": estimate, "lower": float(lower), "upper": float(upper), "confidence": confidence}
        target_confidence[target] = confidence
    label = outcome_label(row, estimates)
    return {
        "deltas": estimates,
        "predictions": intervals,
        "confidence_intervals": {target: {key: value for key, value in interval.items() if key in {"lower", "upper"}} for target, interval in intervals.items()},
        "confidence": float(np.mean(list(target_confidence.values()))),
        "target_confidence": target_confidence,
        "outcome_label": label,
        "model_version": artifact.get("model_version", "unknown"),
    }
