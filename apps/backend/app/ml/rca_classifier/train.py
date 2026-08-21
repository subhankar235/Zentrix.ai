"""Train the multi-label LightGBM root-cause classifier."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from lightgbm import LGBMClassifier
from app.ml.rca_classifier.features import CAUSES, FEATURE_NAMES, build_feature_matrix, build_label_matrix


class MultiLabelLightGBM:
    """One binary LightGBM model per cause, with constant-label fallbacks."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.models: list[LGBMClassifier | None] = []
        self.constants: list[float | None] = []

    def fit(self, values: np.ndarray, labels: np.ndarray) -> "MultiLabelLightGBM":
        for column in range(labels.shape[1]):
            target = labels[:, column]
            unique = np.unique(target)
            if len(unique) < 2:
                self.models.append(None)
                self.constants.append(float(unique[0]))
                continue
            model = LGBMClassifier(
                n_estimators=80,
                learning_rate=0.05,
                num_leaves=15,
                max_depth=4,
                verbosity=-1,
                random_state=self.random_state,
            ).fit(values, target)
            self.models.append(model)
            self.constants.append(None)
        return self

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        columns = []
        for model, constant in zip(self.models, self.constants):
            if model is None:
                columns.append(np.full(len(values), constant, dtype=float))
            else:
                columns.append(model.predict_proba(values)[:, 1])
        return np.column_stack(columns)


def train(
    rows: Sequence[Mapping[str, Any]],
    artifact_path: str | os.PathLike[str] = "rca_model.joblib",
    *,
    random_state: int = 42,
) -> dict[str, Any]:
    values = build_feature_matrix(rows)
    labels = build_label_matrix(rows)
    if len(values) < 2:
        raise ValueError("At least two labeled telemetry rows are required")
    if not labels.any(axis=0).any():
        raise ValueError("Training rows must contain at least one recognized cause label")
    model = MultiLabelLightGBM(random_state).fit(values, labels)
    artifact = {"model": model, "feature_names": FEATURE_NAMES, "causes": CAUSES}
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    _log_mlflow(path, len(values))
    return {"artifact_path": str(path), "rows": len(values), "causes": list(CAUSES)}


def _log_mlflow(path: Path, row_count: int) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        with mlflow.start_run(run_name="rca-lightgbm-multilabel"):
            mlflow.log_param("rows", row_count)
            mlflow.log_artifact(str(path), artifact_path="model")
    except Exception:
        return
