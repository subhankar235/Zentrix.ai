from app.ml.delta_predictor.features import FEATURE_NAMES, TARGET_NAMES, build_feature_matrix, build_target_matrix, extract_features, outcome_label
from app.ml.delta_predictor.predict import predict
from app.ml.delta_predictor.train import train


def _rows(count=30):
    rows = []
    for index in range(count):
        baseline = 100.0 + index * 0.5
        delta = -18.0 if index % 4 == 0 else 12.0 if index % 5 == 0 else 1.0
        strategy = "CREATE_INDEX" if index % 4 == 0 else "DROP_INDEX" if index % 5 == 0 else "ANALYZE"
        rows.append({
            "timestamp": index,
            "strategy": strategy,
            "candidate_sql": "CREATE INDEX idx_orders_status ON orders(status)" if strategy == "CREATE_INDEX" else "ANALYZE orders",
            "baseline_latency": baseline,
            "baseline_p95": baseline * 1.5,
            "baseline_cpu": 40 + index,
            "baseline_io": 1000 + index * 10,
            "baseline_buffer_reads": 500 + index * 3,
            "baseline_buffer_hits": 5000,
            "baseline_rows": 10000 + index * 100,
            "table_size_bytes": 10_000_000 + index * 1000,
            "dead_tuple_ratio": 0.02,
            "idx_scan_ratio": 0.7,
            "delta_latency": delta,
            "delta_p95": delta * 1.3,
            "delta_cpu": delta * 0.4,
            "delta_io": delta * 5,
            "delta_buffer_reads": delta * 2,
            "outcome_label": "GOOD" if delta < 0 else "REGRESSION" if delta > 5 else "NEUTRAL",
        })
    return rows


def test_delta_features_and_targets_are_stable():
    rows = _rows(4)
    assert set(extract_features(rows[0])) == set(FEATURE_NAMES)
    assert build_feature_matrix(rows).shape == (4, len(FEATURE_NAMES))
    assert build_target_matrix(rows).shape == (4, len(TARGET_NAMES))
    assert outcome_label(rows[0]) == "GOOD"


def test_delta_predictor_trains_on_temporal_rows_and_scores_held_out_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    rows = _rows()
    artifact = tmp_path / "delta.joblib"
    result = train(rows, artifact, ensemble_size=3)
    prediction = predict(rows[-1], artifact)

    assert result["rows"] == len(rows)
    assert set(prediction["deltas"]) == set(TARGET_NAMES)
    assert set(prediction["predictions"]) == set(TARGET_NAMES)
    assert all(item["lower"] <= item["estimate"] <= item["upper"] for item in prediction["predictions"].values())
    assert 0 <= prediction["confidence"] <= 1
    assert prediction["outcome_label"] in {"GOOD", "BAD", "NEUTRAL", "REGRESSION"}


def test_delta_predictor_rejects_too_few_rows(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        train(_rows(7), tmp_path / "delta.joblib")
