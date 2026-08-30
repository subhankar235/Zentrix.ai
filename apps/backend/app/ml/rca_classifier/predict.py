"""Inference and deterministic causal ranking for root-cause predictions."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.ml.rca_classifier.features import CAUSES, build_feature_matrix


def _load(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return joblib.load(Path(path or os.getenv("RCA_MODEL_PATH", "rca_model.joblib")))


def rank_causes(
    probabilities: Mapping[str, float],
    evidence_strength: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Rank causes without changing model probabilities or inventing evidence."""
    evidence_strength = evidence_strength or {}
    ranked = []
    for cause, probability in probabilities.items():
        score = float(np.clip(probability, 0.0, 1.0))
        if evidence_strength.get(cause) is not None:
            score *= float(np.clip(evidence_strength[cause], 0.0, 1.0))
        rank = "PRIMARY" if score >= 0.65 else "CONTRIBUTING" if score >= 0.35 else "CORRELATED" if score >= 0.15 else "UNRELATED"
        ranked.append({"cause": cause, "probability": float(np.clip(probability, 0.0, 1.0)), "score": score, "rank": rank})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _evidence_strength(features: Mapping[str, Any]) -> dict[str, float]:
    """Give direct live signals priority over weak classifier probabilities."""
    def ratio(value: Any, scale: float) -> float:
        try:
            return float(np.clip(float(value or 0) / scale, 0.0, 1.0))
        except (TypeError, ValueError):
            return 0.0

    return {
        "STALE_STATISTICS": max(ratio(features.get("analyze_age"), 24), ratio(features.get("cardinality_error"), 2)),
        "PLAN_FLIP": 1.0 if float(features.get("plan_flip") or 0) > 0 else 0.0,
        "CARDINALITY_MISESTIMATION": ratio(features.get("cardinality_error"), 2),
        "LOCK_CONTENTION": ratio(features.get("lock_wait_seconds"), 5),
        "VACUUM_LAG": ratio(features.get("vacuum_age"), 24),
        "BLOAT": ratio(features.get("dead_tuple_ratio"), 0.2),
        "INDEX_MISSING": 1.0 if float(features.get("missing_index") or 0) > 0 else 0.0,
        "BUFFER_PRESSURE": ratio(features.get("buffer_read_ratio"), 0.5),
        "TEMP_SPILL": ratio(features.get("temp_io"), 1000),
        "CONNECTION_CONTENTION": ratio(features.get("connection_saturation"), 100),
        "IO_SATURATION": ratio(features.get("wal_rate"), 1_000_000),
    }


def predict(
    features: Mapping[str, Any],
    model_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    artifact = _load(model_path)
    values = build_feature_matrix([features])
    model = artifact["model"]
    raw = model.predict_proba(values)
    # OneVsRest returns either an ndarray or a list for edge-case estimators.
    probabilities = np.asarray(raw, dtype=object)
    if probabilities.ndim == 2:
        probabilities = probabilities[0]
    probabilities = [float(value[1] if isinstance(value, (list, tuple, np.ndarray)) and len(value) > 1 else value) for value in probabilities]
    probability_map = {
        cause: probability
        for cause, probability in zip(artifact.get("causes", CAUSES), np.clip(probabilities, 0.0, 1.0))
        if cause != "UNKNOWN"
    }
    ranked = rank_causes(probability_map, _evidence_strength(features))
    # UNKNOWN is a conservative residual fallback, not a trained class. This
    # prevents the normal baseline rows from overwhelming every known cause.
    max_known = max(probability_map.values(), default=0.0)
    probability_map["UNKNOWN"] = float(np.clip(1.0 - max_known, 0.0, 1.0))
    ranked = rank_causes(probability_map, _evidence_strength(features))
    return {"probabilities": probability_map, "ranked_causes": ranked}
