"""Train the Isolation Forest anomaly model."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.ml.anomaly.features import FEATURE_NAMES, build_feature_matrix


def train(
    rows: Sequence[Mapping[str, Any]],
    artifact_path: str | os.PathLike[str] = "anomaly_model.joblib",
    *,
    contamination: float = 0.05,
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit and persist an Isolation Forest, logging the artifact to MLflow."""
    values = build_feature_matrix(rows)
    if len(values) < 2:
        raise ValueError("At least two telemetry rows are required")
    median = np.median(values, axis=0)
    mad = np.median(np.abs(values - median), axis=0)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
    ).fit(values)
    artifact = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "median": median,
        "mad": mad,
        "contamination": contamination,
    }
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    _log_mlflow(path, len(values), contamination)
    return {"artifact_path": str(path), "rows": len(values), "feature_names": list(FEATURE_NAMES)}


def _log_mlflow(path: Path, row_count: int, contamination: float) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        with mlflow.start_run(run_name="anomaly-isolation-forest"):
            mlflow.log_params({"rows": row_count, "contamination": contamination})
            mlflow.log_artifact(str(path), artifact_path="model")
    except Exception:
        # Local training must remain usable when the optional tracking server is down.
        return


if __name__ == "__main__":
    raise SystemExit("Import train() and provide telemetry rows")
