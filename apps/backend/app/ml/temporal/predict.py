"""Inference for the promoted LSTM autoencoder."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.ml.temporal.train import LSTMAutoencoder


def _load(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    return torch.load(path or os.getenv("TEMPORAL_MODEL_PATH", "temporal_model.pt"), map_location="cpu")


def predict(
    window: Sequence[Sequence[float]] | np.ndarray,
    model_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    artifact = _load(model_path)
    values = torch.as_tensor(np.asarray(window, dtype=np.float32)).unsqueeze(0)
    if values.shape[1] != artifact["timesteps"] or values.shape[2] != artifact["input_size"]:
        raise ValueError("window shape does not match the trained temporal model")
    model = LSTMAutoencoder(artifact["input_size"], artifact["hidden_size"], artifact["latent_size"])
    model.load_state_dict(artifact["state_dict"])
    model.eval()
    with torch.no_grad():
        reconstruction_error = float(((model(values) - values) ** 2).mean().item())
    threshold = float(artifact["threshold"])
    probability = 1.0 / (1.0 + math.exp(-8.0 * (reconstruction_error / max(threshold, 1e-8) - 1.0)))
    return {
        "anomaly_probability": float(np.clip(probability, 0.0, 1.0)),
        "reconstruction_error": reconstruction_error,
        "threshold": threshold,
        "is_anomaly": reconstruction_error > threshold,
    }
