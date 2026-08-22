import numpy as np

from app.ml.anomaly.features import FEATURE_NAMES, build_feature_matrix
from app.ml.anomaly.predict import predict as predict_anomaly
from app.ml.anomaly.train import train as train_anomaly
from app.ml.rca_classifier.predict import predict as predict_rca, rank_causes
from app.ml.rca_classifier.train import train as train_rca
from app.ml.temporal.features import build_windows
from app.ml.temporal.predict import predict as predict_temporal
from app.ml.temporal.train import train as train_temporal


def _telemetry_rows(count=24):
    return [
        {
            "latency_p50": 10 + index,
            "latency_p95": 20 + index * 2,
            "execution_time": 15 + index,
            "planning_time": 2,
            "buffer_hits": 1000,
            "buffer_reads": 100 + index,
            "dead_tuple_ratio": 0.01 + index / 1000,
            "cache_hit_ratio": 0.9,
            "wal_rate": 10 + index,
            "table_growth_rate": 0.1,
            "vacuum_age": 60,
            "analyze_age": 120,
            "cardinality_error": index / 10,
            "plan_flip": int(index % 8 == 0),
        }
        for index in range(count)
    ]


def test_anomaly_model_trains_and_returns_interpretable_probability(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    rows = _telemetry_rows()
    assert build_feature_matrix(rows).shape == (24, 17)
    artifact = tmp_path / "anomaly.joblib"

    train_anomaly(rows, artifact, contamination=0.1)
    result = predict_anomaly(rows[-1], artifact)

    assert 0 <= result["anomaly_score"] <= 1
    assert set(result["robust_z_scores"]) == set(FEATURE_NAMES)
    assert isinstance(result["is_anomaly"], bool)


def test_temporal_lstm_model_trains_and_scores_window(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    rows = _telemetry_rows(12)
    windows = build_windows(rows, window_size=4)
    assert windows.shape == (9, 4, 17)
    artifact = tmp_path / "temporal.pt"

    train_temporal(windows, artifact, epochs=1, hidden_size=4, latent_size=2)
    result = predict_temporal(windows[-1], artifact)

    assert 0 <= result["anomaly_probability"] <= 1
    assert result["reconstruction_error"] >= 0


def test_rca_classifier_returns_probabilities_and_causal_ranks(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    rows = [
        {**row, "labels": ["PLAN_FLIP"] if index % 2 else ["LOCK_CONTENTION"]}
        for index, row in enumerate(_telemetry_rows())
    ]
    artifact = tmp_path / "rca.joblib"

    train_rca(rows, artifact)
    result = predict_rca(rows[-1], artifact)

    assert set(result["probabilities"]) >= {"PLAN_FLIP", "LOCK_CONTENTION"}
    assert all(0 <= value <= 1 for value in result["probabilities"].values())
    assert result["ranked_causes"]
    assert rank_causes({"PLAN_FLIP": 0.9})[0]["rank"] == "PRIMARY"
