"""Feature 3 L1 Workload Degradation Forecasting Inference.

Generates multi-step degradation probability curves (degradation_probability(t))
and conformal confidence intervals from input telemetry history.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 3 L1.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.forecasting.features import FEATURE_NAMES, build_feature_matrix, extract_telemetry_features

logger = get_logger(__name__)


def _load_model(model_path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    """Load serialized L1 forecasting artifact."""
    target_path = Path(model_path or os.getenv("FORECASTING_MODEL_PATH", "forecasting_model.joblib"))
    if not target_path.is_absolute() and not target_path.exists():
        backend_root = Path(__file__).resolve().parents[3]
        candidates = [backend_root / target_path]
        # The checked-in local artifact is used only as a development fallback;
        # promoted deployments should point FORECASTING_MODEL_PATH at .artifacts.
        if target_path.name == "forecasting_model.joblib":
            candidates.append(backend_root / "forecasting_model.joblib")
        target_path = next((candidate for candidate in candidates if candidate.exists()), target_path)
    if not target_path.exists():
        return None
    try:
        return joblib.load(target_path)
    except Exception as exc:
        logger.warning(f"Failed to load forecasting artifact at {target_path}: {exc}")
        return None


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0))))


def predict(
    telemetry_history: Sequence[Mapping[str, Any]],
    horizon_hours: int = 168,  # Default 7 days (168h) per PRD §5
    model_path: str | os.PathLike[str] | None = None,
    current_time: datetime | None = None,
    action_threshold: float = 0.40,
) -> dict[str, Any]:
    """Generate future degradation probability curve and conformal prediction intervals.

    Returns:
        Dict containing:
            - degradation_probability: scalar overall risk (0.0 to 1.0)
            - is_flagged_for_action: bool (True if degradation risk exceeds threshold)
            - probability_curve: list of hourly DegradationCurvePoint dicts
            - forecast_window_start / end: ISO timestamps
            - model_version: str
    """
    now = current_time or datetime.now(timezone.utc)
    if telemetry_history:
        latest_ts = telemetry_history[-1].get("timestamp")
        if isinstance(latest_ts, datetime):
            now = latest_ts
        elif isinstance(latest_ts, str):
            try:
                now = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
            except Exception:
                pass

    window_start = now
    window_end = now + timedelta(hours=horizon_hours)

    if len(telemetry_history) < 2:
        curve = [
            {
                "timestamp": (window_start + timedelta(hours=h)).isoformat(),
                "horizon_hours": h,
                "predicted_probability": 0.0,
                "confidence_lower": 0.0,
                "confidence_upper": 1.0,
                "projected_delta_ratio": 0.0,
            }
            for h in range(1, horizon_hours + 1, 6 if horizon_hours > 48 else 1)
        ]
        return {
            "degradation_probability": 0.0,
            "is_flagged_for_action": False,
            "forecast_window_start": window_start.isoformat(),
            "forecast_window_end": window_end.isoformat(),
            "probability_curve": curve,
            "model_version": "unavailable",
            "conformal_quantile": None,
            "threshold_probability": float(action_threshold),
            "threshold_day": None,
            "confidence": 0.0,
            "data_quality": "insufficient_telemetry",
        }

    features = extract_telemetry_features(telemetry_history, current_time=now)
    X = build_feature_matrix([features])

    artifact = _load_model(model_path)

    if artifact is not None and "model" in artifact:
        model = artifact["model"]
        q_conformal = float(artifact.get("q_conformal", 0.15))
        version = str(artifact.get("version", "l1_v1"))

        # Base 24h delta prediction
        base_delta = float(model.predict(X)[0])
        probability_model = artifact.get("probability_model")
        base_probability = (
            float(probability_model.predict_proba(X)[0, 1])
            if probability_model is not None and hasattr(probability_model, "predict_proba")
            else _sigmoid((base_delta - 0.15) * 5.0)
        )
    else:
        # Heuristic statistical fallback for cold start before first model train
        p95_growth = float(features.get("growth_24h_p95", 0.0))
        dead_tuple_ratio = float(features.get("current_dead_tuple_ratio", 0.05))
        base_delta = p95_growth * 1.5 + dead_tuple_ratio * 0.5
        base_probability = _sigmoid((base_delta - 0.15) * 5.0)
        q_conformal = 0.20
        version = "heuristic_v0"

    # Project degradation probability curve over horizon hours
    curve: list[dict[str, Any]] = []
    max_prob = 0.0

    # Hourly or multi-hour step progression
    step_hours = 6 if horizon_hours > 48 else 1
    for h in range(1, horizon_hours + 1, step_hours):
        t_point = window_start + timedelta(hours=h)

        # Time-scaling: compounding effect over horizon
        time_factor = (h / 24.0) ** 0.8
        projected_delta = base_delta * (1.0 + 0.05 * time_factor)

        # Conformal prediction interval
        lower_delta = projected_delta - q_conformal
        upper_delta = projected_delta + q_conformal

        # Map delta to probability of degradation (> 20% latency increase)
        point_prob = _sigmoid((projected_delta - 0.15) * 5.0)
        if artifact is not None and "probability_model" in artifact and artifact.get("probability_model") is not None:
            point_prob = float(np.clip(base_probability + (point_prob - base_probability) * (1.0 + 0.05 * time_factor), 0.0, 1.0))
        lower_prob = _sigmoid((lower_delta - 0.15) * 5.0)
        upper_prob = _sigmoid((upper_delta - 0.15) * 5.0)

        max_prob = max(max_prob, point_prob)

        curve.append({
            "timestamp": t_point.isoformat(),
            "horizon_hours": h,
            "predicted_probability": float(point_prob),
            "confidence_lower": float(lower_prob),
            "confidence_upper": float(upper_prob),
            "projected_delta_ratio": float(projected_delta),
        })

    is_flagged = bool(max_prob >= action_threshold)
    threshold_hour = next(
        (point["horizon_hours"] for point in curve if point["predicted_probability"] >= action_threshold),
        None,
    )
    confidence = float(max(0.0, min(1.0, 1.0 - q_conformal)))

    return {
        "degradation_probability": float(max_prob),
        "is_flagged_for_action": is_flagged,
        "forecast_window_start": window_start.isoformat(),
        "forecast_window_end": window_end.isoformat(),
        "probability_curve": curve,
        "model_version": version,
        "conformal_quantile": float(q_conformal),
        "threshold_probability": float(action_threshold),
        "threshold_day": float(threshold_hour / 24.0) if threshold_hour is not None else None,
        "confidence": confidence,
        "data_quality": "model" if artifact is not None else "cold_start_heuristic",
    }
