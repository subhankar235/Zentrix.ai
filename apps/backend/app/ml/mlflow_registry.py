"""Small MLflow adapter shared by training and model deployment code."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping


def tracking_uri() -> str:
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def log_training_run(
    *,
    run_name: str,
    artifact_path: Path,
    experiment_name: str,
    model_name: str,
    params: Mapping[str, Any] | None = None,
    metrics: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Log a complete candidate run and register it in MLflow.

    Registration is intentionally best-effort for local unit tests using a
    file-based tracking URI. Production promotion is gated on the returned
    ``registered_version`` being present.
    """
    import mlflow

    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        if params:
            mlflow.log_params({key: str(value) for key, value in params.items()})
        if metrics:
            mlflow.log_metrics({key: float(value) for key, value in metrics.items()})
        mlflow.log_artifact(str(artifact_path), artifact_path="model")
        run_id = run.info.run_id

    result: dict[str, Any] = {"run_id": run_id, "registered_version": None}
    try:
        registered = mlflow.register_model(f"runs:/{run_id}/model", model_name)
        result["registered_version"] = str(registered.version)
    except Exception as exc:
        result["registration_error"] = str(exc)
    return result


def promote_registered_model(
    *,
    model_name: str,
    destination: Path,
    version: str,
) -> dict[str, Any]:
    """Download a registered candidate and assign it the ``champion`` alias."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient(tracking_uri=tracking_uri())
    model_version = client.get_model_version(model_name, version)
    source = mlflow.artifacts.download_artifacts(
        run_id=model_version.run_id,
        artifact_path="model/" + destination.name,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    client.set_registered_model_alias(model_name, "champion", version)
    return {"model_name": model_name, "version": str(version), "path": str(destination)}


def champion_metric(model_name: str, metric_name: str) -> float | None:
    """Read a metric from the currently aliased champion model."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient(tracking_uri=tracking_uri())
    try:
        version = client.get_model_version_by_alias(model_name, "champion")
    except Exception:
        return None
    run = client.get_run(version.run_id)
    value = run.data.metrics.get(metric_name)
    return float(value) if value is not None else None
