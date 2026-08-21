"""Train a PyTorch LSTM autoencoder over telemetry windows."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from app.ml.temporal.features import build_windows


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 32, latent_size: int = 16) -> None:
        super().__init__()
        self.encoder = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.to_latent = nn.Linear(hidden_size, latent_size)
        self.from_latent = nn.Linear(latent_size, hidden_size)
        self.decoder = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, input_size)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        encoded, _ = self.encoder(values)
        latent = self.to_latent(encoded[:, -1])
        repeated = self.from_latent(latent).unsqueeze(1).repeat(1, values.size(1), 1)
        decoded, _ = self.decoder(repeated)
        return self.output(decoded)


def train(
    windows: np.ndarray | Sequence[Sequence[Sequence[float]]],
    artifact_path: str | os.PathLike[str] = "temporal_model.pt",
    *,
    epochs: int = 10,
    hidden_size: int = 32,
    latent_size: int = 16,
    learning_rate: float = 1e-3,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Train on windows shaped ``(samples, timesteps, features)``."""
    torch.manual_seed(random_seed)
    values = torch.as_tensor(np.asarray(windows, dtype=np.float32))
    if values.ndim != 3 or values.shape[0] < 2:
        raise ValueError("At least two temporal windows are required")
    model = LSTMAutoencoder(values.shape[2], hidden_size, latent_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(max(1, epochs)):
        optimizer.zero_grad()
        loss = loss_fn(model(values), values)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        errors = ((model(values) - values) ** 2).mean(dim=(1, 2)).numpy()
    threshold = float(np.quantile(errors, 0.95))
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "input_size": int(values.shape[2]),
            "timesteps": int(values.shape[1]),
            "hidden_size": hidden_size,
            "latent_size": latent_size,
            "threshold": threshold,
        },
        path,
    )
    _log_mlflow(path, len(values), epochs, threshold)
    return {"artifact_path": str(path), "windows": len(values), "threshold": threshold}


def train_from_rows(
    rows: Sequence[dict[str, Any]],
    artifact_path: str | os.PathLike[str] = "temporal_model.pt",
    *,
    window_size: int = 30,
    **kwargs: Any,
) -> dict[str, Any]:
    return train(build_windows(rows, window_size=window_size), artifact_path, **kwargs)


def _log_mlflow(path: Path, window_count: int, epochs: int, threshold: float) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        with mlflow.start_run(run_name="temporal-lstm-autoencoder"):
            mlflow.log_params({"windows": window_count, "epochs": epochs})
            mlflow.log_metric("reconstruction_threshold", threshold)
            mlflow.log_artifact(str(path), artifact_path="model")
    except Exception:
        return
