"""Train the LightGBM query-performance delta predictor."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.ml.delta_predictor.features import FEATURE_NAMES, TARGET_NAMES, build_feature_matrix, build_target_matrix, outcome_label


class ConstantRegressor:
    """Pickleable fallback for a target with insufficient variation."""

    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)

    def predict(self, values: np.ndarray) -> np.ndarray:
        return np.full(len(values), self.value, dtype=float)


def _fit_ensemble(values: np.ndarray, target: np.ndarray, *, random_state: int, members: int) -> list[Any]:
    models: list[Any] = []
    rng = np.random.default_rng(random_state)
    for member in range(members):
        indices = rng.integers(0, len(values), size=len(values))
        if np.ptp(target[indices]) < 1e-12:
            models.append(ConstantRegressor(float(np.mean(target[indices]))))
            continue
        models.append(LGBMRegressor(
            n_estimators=120,
            learning_rate=0.04,
            num_leaves=min(15, max(3, len(values) // 3)),
            max_depth=5,
            min_child_samples=max(3, min(20, len(values) // 5)),
            reg_lambda=0.2,
            verbosity=-1,
            random_state=random_state + member,
        ).fit(values[indices], target[indices]))
    return models


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    result = {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
    }
    result["r2"] = float(r2_score(actual, predicted)) if np.ptp(actual) > 1e-12 else 0.0
    return result


def train(
    rows: Sequence[Mapping[str, Any]],
    artifact_path: str | os.PathLike[str] = "delta_predictor.joblib",
    *,
    random_state: int = 42,
    ensemble_size: int = 7,
    validation_fraction: float = 0.2,
) -> dict[str, Any]:
    """Fit and persist an ensemble using a temporal holdout for validation."""
    if len(rows) < 8:
        raise ValueError("At least eight chronological experiment rows are required")
    if not 0.1 <= validation_fraction < 0.5:
        raise ValueError("validation_fraction must be between 0.1 and 0.5")
    if ensemble_size < 3:
        raise ValueError("ensemble_size must be at least 3")
    values = build_feature_matrix(rows)
    targets = build_target_matrix(rows)
    split = min(len(rows) - 2, max(2, int(len(rows) * (1 - validation_fraction))))
    train_values, valid_values = values[:split], values[split:]
    train_targets, valid_targets = targets[:split], targets[split:]
    validation_models = [_fit_ensemble(train_values, train_targets[:, index], random_state=random_state + index * 101, members=ensemble_size) for index in range(len(TARGET_NAMES))]
    validation_predictions = np.column_stack([np.mean([model.predict(valid_values) for model in models], axis=0) for models in validation_models])
    validation_metrics = {target: _metrics(valid_targets[:, index], validation_predictions[:, index]) for index, target in enumerate(TARGET_NAMES)}

    models = [_fit_ensemble(values, targets[:, index], random_state=random_state + index * 101, members=ensemble_size) for index in range(len(TARGET_NAMES))]
    residual_scales = np.std(targets - np.column_stack([np.mean([model.predict(values) for model in target_models], axis=0) for target_models in models]), axis=0, ddof=1)
    artifact = {
        "models": models,
        "feature_names": FEATURE_NAMES,
        "target_names": TARGET_NAMES,
        "residual_scales": np.nan_to_num(residual_scales, nan=0.0),
        "model_version": "delta-lgbm-ensemble-v1",
        "validation_metrics": validation_metrics,
        "outcome_labels": sorted({outcome_label(row) for row in rows}),
    }
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    _log_mlflow(path, len(rows), split, validation_metrics)
    return {"artifact_path": str(path), "rows": len(rows), "feature_names": list(FEATURE_NAMES), "targets": list(TARGET_NAMES), "validation_metrics": validation_metrics}


def _log_mlflow(path: Path, row_count: int, split: int, metrics: Mapping[str, Mapping[str, float]]) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        with mlflow.start_run(run_name="delta-predictor-lightgbm"):
            mlflow.log_params({"rows": row_count, "temporal_train_rows": split, "targets": len(TARGET_NAMES)})
            mlflow.log_metrics({f"{target}_{name}": value for target, values in metrics.items() for name, value in values.items()})
            mlflow.log_artifact(str(path), artifact_path="model")
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit("Import train() and provide optimization experiment rows")
