"""Resolve promoted, real-data Feature 1 model artifacts.

Live diagnosis must never manufacture training data. Model artifacts are
deployment inputs; missing artifacts are reported explicitly to the caller.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _artifact_path(environment_name: str, default_name: str) -> Path:
    settings = get_settings()
    configured = os.getenv(environment_name) or getattr(settings, environment_name, None)
    path = Path(configured or default_name)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


def model_paths() -> dict[str, Path]:
    return {
        "anomaly": _artifact_path("ANOMALY_MODEL_PATH", ".artifacts/anomaly_model.joblib"),
        "rca": _artifact_path("RCA_MODEL_PATH", ".artifacts/rca_model.joblib"),
        "temporal": _artifact_path("TEMPORAL_MODEL_PATH", ".artifacts/temporal_model.pt"),
        "manifest": _artifact_path("FEATURE1_MANIFEST_PATH", ".artifacts/manifest.json"),
    }


def ensure_feature1_models() -> dict[str, Any]:
    """Describe deployed model artifacts without creating replacement data."""
    paths = model_paths()
    missing = [name for name, path in paths.items() if not path.is_file()]
    manifest: dict[str, Any] = {}
    if not missing:
        try:
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            if manifest.get("source") != "fault_lab" or manifest.get("status") != "promoted":
                missing.append("manifest")
        except (OSError, json.JSONDecodeError):
            missing.append("manifest")
    return {
        "status": "ready" if not missing else "missing_artifact",
        "source": manifest.get("source") if not missing else "none",
        "missing": missing,
        "paths": {name: str(path) for name, path in paths.items()},
        "manifest": manifest if not missing else None,
    }
