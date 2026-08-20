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
    probability_map = dict(zip(artifact.get("causes", CAUSES), np.clip(probabilities, 0.0, 1.0)))
    ranked = rank_causes(probability_map)
    return {"probabilities": probability_map, "ranked_causes": ranked}
