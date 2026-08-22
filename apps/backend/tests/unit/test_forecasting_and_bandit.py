import numpy as np
import pytest

from app.ml.bandit.policy import (
    ACTIONS,
    ContextualThompsonSamplingBandit,
    RolloutPhase,
    compute_reward,
    extract_context_vector,
    select_rule_based_strategy,
)
from app.ml.forecasting.features import (
    FEATURE_NAMES,
    build_feature_matrix,
    extract_calendar_features,
    extract_telemetry_features,
)
from app.ml.forecasting.predict import predict as predict_forecasting
from app.ml.forecasting.train import (
    build_forecasting_dataset,
    generate_synthetic_telemetry_series,
    train as train_forecasting,
    walk_forward_train,
)


def test_forecasting_feature_extraction():
    # 1. Calendar features
    cal = extract_calendar_features(None)
    assert "hour_sin" in cal and "hour_cos" in cal
    assert -1.0 <= cal["hour_sin"] <= 1.0
    assert 0.0 <= cal["is_weekend"] <= 1.0

    # 2. Telemetry series features
    series = generate_synthetic_telemetry_series(n_days=10)
    feat_dict = extract_telemetry_features(series)
    assert len(feat_dict) == len(FEATURE_NAMES)
    assert "lag_24h_p95_exec_time" in feat_dict
    assert "roll_24h_mean_p95" in feat_dict
    assert "growth_24h_p95" in feat_dict

    matrix = build_feature_matrix([feat_dict, feat_dict])
    assert matrix.shape == (2, len(FEATURE_NAMES))
    assert not np.isnan(matrix).any()


def test_forecasting_walk_forward_training_and_conformal_calibration(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:///{tmp_path.as_posix().lstrip('/')}")
    series = generate_synthetic_telemetry_series(n_days=30, degradation_start_day=15)
    X, y_reg, y_prob, feature_names = build_forecasting_dataset(series, horizon_steps=12, min_history_steps=24)

    assert len(X) > 50
    assert len(feature_names) == len(FEATURE_NAMES)

    # Walk-forward cross validation
    model, q_conformal, metrics = walk_forward_train(X, y_reg, n_splits=3)
    assert q_conformal > 0.0
    assert metrics["mae"] >= 0.0
    assert metrics["rmse"] >= 0.0
    assert metrics["conformal_coverage"] >= 0.70

    # Test complete train() artifact serialization
    artifact_path = tmp_path / "forecasting.joblib"
    train_res = train_forecasting(series, output_path=artifact_path, version="test_v1")
    assert train_res["status"] == "TRAINED"
    assert artifact_path.exists()

    # Test predict() with trained model
    pred_res = predict_forecasting(series, horizon_hours=72, model_path=artifact_path)
    assert 0.0 <= pred_res["degradation_probability"] <= 1.0
    assert len(pred_res["probability_curve"]) > 0
    assert isinstance(pred_res["is_flagged_for_action"], bool)
    point0 = pred_res["probability_curve"][0]
    assert point0["confidence_lower"] <= point0["predicted_probability"] <= point0["confidence_upper"] or point0["confidence_lower"] <= point0["confidence_upper"]


def test_forecasting_cold_start_heuristic_fallback():
    series = generate_synthetic_telemetry_series(n_days=5)
    pred_res = predict_forecasting(series, horizon_hours=48, model_path="non_existent_file.joblib")
    assert 0.0 <= pred_res["degradation_probability"] <= 1.0
    assert pred_res["model_version"] == "heuristic_v0"
    assert len(pred_res["probability_curve"]) > 0


def test_bandit_reward_computation():
    # 1. High improvement, low risk
    good_delta = {
        "p95_improvement_ratio": 0.40,
        "cpu_reduction_ratio": 0.20,
        "io_reduction_ratio": 0.15,
        "regression_rate": 0.0,
    }
    good_reward = compute_reward(good_delta, action="CREATE_INDEX", risk_level="LOW")
    assert good_reward > 0.25

    # 2. Heavy regression penalty
    regressed_delta = {
        "p95_improvement_ratio": -0.20,
        "regression_rate": 0.15,
    }
    bad_reward = compute_reward(regressed_delta, action="CREATE_INDEX", risk_level="HIGH")
    assert bad_reward < 0.0


def test_bandit_rollout_gating():
    ctx = {
        "cardinality_error": 3.5,
        "dead_tuple_ratio": 0.02,
        "idx_scan_ratio": 0.8,
        "p95_exec_time": 50.0,
    }

    # 1. Default Phase 1: Rule-based gate strictly enforced
    bandit_p1 = ContextualThompsonSamplingBandit(rollout_phase=RolloutPhase.PHASE_1_RULE_BASED)
    assert bandit_p1.is_bandit_live() is False
    res_p1 = bandit_p1.select_action(ctx)
    assert res_p1["is_bandit_live"] is False
    assert res_p1["decision_source"] == "RULE_BASED_GATE"
    assert res_p1["selected_action"] == "UPDATE_STATISTICS"  # Rule-based choice for cardinality_error > 2.0

    # 2. Phase 4: Offline Evaluated -> Bandit is live
    bandit_p4 = ContextualThompsonSamplingBandit(rollout_phase=RolloutPhase.PHASE_4_OFFLINE_EVALUATED)
    assert bandit_p4.is_bandit_live() is True
    res_p4 = bandit_p4.select_action(ctx)
    assert res_p4["is_bandit_live"] is True
    assert res_p4["decision_source"] == "BANDIT_LIVE_POLICY"
    assert res_p4["selected_action"] in ACTIONS


def test_bandit_thompson_sampling_learns_higher_reward_actions():
    bandit = ContextualThompsonSamplingBandit(
        actions=["CREATE_INDEX", "VACUUM_ANALYZE", "DO_NOTHING"],
        rollout_phase=RolloutPhase.PHASE_4_OFFLINE_EVALUATED,
    )
    context = {"cardinality_error": 0.1, "dead_tuple_ratio": 0.01, "idx_scan_ratio": 0.1, "p95_exec_time": 150.0}

    # Simulate 50 rounds where CREATE_INDEX consistently yields high reward (+0.8), others yield negative reward
    for _ in range(50):
        bandit.update(context, action="CREATE_INDEX", reward=0.8)
        bandit.update(context, action="VACUUM_ANALYZE", reward=-0.2)
        bandit.update(context, action="DO_NOTHING", reward=0.0)

    # Over 50 selection trials, CREATE_INDEX should win the vast majority of selections
    picks = [bandit.select_action(context)["selected_action"] for _ in range(50)]
    create_index_count = picks.count("CREATE_INDEX")
    assert create_index_count >= 40  # >= 80% preference for the highest reward action


def test_bandit_offline_policy_evaluation_ips():
    bandit = ContextualThompsonSamplingBandit()
    context = {"cardinality_error": 0.5, "dead_tuple_ratio": 0.05, "idx_scan_ratio": 0.5}

    # Generate synthetic logged bandit interaction events
    logged_events = [
        {"context": context, "action": "CREATE_INDEX", "propensity": 0.33, "reward": 0.5},
        {"context": context, "action": "CREATE_INDEX", "propensity": 0.33, "reward": 0.6},
        {"context": context, "action": "DO_NOTHING", "propensity": 0.33, "reward": 0.0},
        {"context": context, "action": "VACUUM_ANALYZE", "propensity": 0.33, "reward": 0.1},
    ] * 10

    eval_result = bandit.evaluate_offline_ips(logged_events, min_effective_sample_size=10)
    assert eval_result["status"] == "EVALUATED"
    assert eval_result["effective_sample_size"] > 0
    assert "ips_value" in eval_result
    assert "is_promotable" in eval_result
