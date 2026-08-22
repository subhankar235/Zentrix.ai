import pytest

from app.tools.policy_engine import PolicyConfig, evaluate


def _good_verification_result():
    return {
        "sample_size": 20,
        "baseline_p95": 100.0,
        "candidate_p95": 70.0,  # 30% improvement
        "p95_improvement_ratio": 0.30,
        "ci_excludes_zero": True,
        "ci_upper": -5.0,
        "regression_rate": 0.02,  # 2% regression <= 5% max
        "write_latency_increase_ratio": 0.04,  # 4% <= 15% max
        "storage_increase_ratio": 0.08,  # 8% <= 20% max
        "skeptic_score": 0.15,  # 0.15 < 0.40 max
    }


def test_policy_engine_approves_valid_verified_candidate():
    res = evaluate(_good_verification_result())
    assert res["verdict"] == "APPROVE"
    assert res["status"] == "VERIFIED"
    assert res["canary_eligible"] is True
    assert len(res["violated_rules"]) == 0
    assert len(res["passed_rules"]) == 7


def test_policy_engine_blocks_when_p95_improvement_is_insufficient():
    data = {**_good_verification_result(), "p95_improvement_ratio": 0.04}
    res = evaluate(data)
    assert res["verdict"] == "BLOCK"
    assert res["status"] == "REJECTED"
    assert res["canary_eligible"] is False
    assert any("p95 improvement" in rule for rule in res["violated_rules"])


def test_policy_engine_blocks_when_regression_rate_is_too_high():
    data = {**_good_verification_result(), "regression_rate": 0.12}
    res = evaluate(data)
    assert res["verdict"] == "BLOCK"
    assert any("regression rate" in rule for rule in res["violated_rules"])


def test_policy_engine_blocks_when_write_latency_overhead_breaches_threshold():
    data = {**_good_verification_result(), "write_latency_increase_ratio": 0.25}
    res = evaluate(data)
    assert res["verdict"] == "BLOCK"
    assert any("Write latency" in rule for rule in res["violated_rules"])


def test_policy_engine_blocks_when_storage_growth_exceeds_threshold():
    data = {**_good_verification_result(), "storage_increase_ratio": 0.35}
    res = evaluate(data)
    assert res["verdict"] == "BLOCK"
    assert any("Storage growth" in rule for rule in res["violated_rules"])


def test_policy_engine_blocks_when_skeptic_score_is_too_high():
    data = {**_good_verification_result(), "skeptic_score": 0.65}
    res = evaluate(data)
    assert res["verdict"] == "BLOCK"
    assert any("Skeptic" in rule for rule in res["violated_rules"])


def test_policy_engine_downgrades_to_conditional_when_underpowered():
    data = {**_good_verification_result(), "sample_size": 4}
    res = evaluate(data)
    assert res["verdict"] == "CONDITIONAL"
    assert res["status"] == "CONDITIONAL"
    assert res["canary_eligible"] is False
    assert any("Sample size" in rule for rule in res["violated_rules"])


def test_policy_engine_custom_config():
    custom_cfg = PolicyConfig(min_p95_improvement_ratio=0.50)  # Requires 50% improvement
    res = evaluate(_good_verification_result(), config=custom_cfg)
    assert res["verdict"] == "BLOCK"  # 30% is not enough for 50% threshold

