import pytest

from app.agents.graph_simulation import build_simulation_graph, run_simulation, simulation_graph


def _fixture_candidate():
    return {
        "id": "cand-123",
        "name": "idx_orders_user_created",
        "sql": "CREATE INDEX idx_orders_user_created ON orders(user_id, created_at)",
        "baseline_p95": 120.0,
        "candidate_p95": 75.0,  # ~37% improvement
        "sample_size": 25,
        "regression_rate": 0.01,
        "write_latency_increase_ratio": 0.03,
        "storage_increase_ratio": 0.05,
        "skeptic_score": 0.10,
    }


def test_simulation_graph_executes_all_agent_stages_and_approves():
    res = simulation_graph.invoke({"candidate": _fixture_candidate()})

    # 1. Experiment Agent Output
    assert "experiment_results" in res
    assert res["experiment_results"]["sample_size"] == 25

    # 2. ML Scientist Agent Output
    assert "ml_prediction" in res
    assert res["ml_prediction"]["agent"] == "ML_SCIENTIST"
    assert res["ml_prediction"]["confidence"] > 0.5

    # 3. Skeptic Agent Output
    assert "skeptic_report" in res
    assert res["skeptic_report"]["agent"] == "SKEPTIC"
    assert res["skeptic_report"]["is_adversarially_approved"] is True

    # 4. Verification Agent Output
    assert "verification_report" in res
    assert res["verification_report"]["agent"] == "VERIFICATION"
    assert res["verification_report"]["verdict"] == "VERIFIED"

    # 5. Policy Agent Output
    assert "policy_verdict" in res
    assert res["policy_verdict"]["verdict"] == "APPROVE"
    assert res["policy_verdict"]["status"] == "VERIFIED"
    assert res["policy_verdict"]["canary_eligible"] is True

    # 6. Deployment Agent Output
    assert "deployment_plan" in res
    assert res["deployment_plan"]["status"] == "READY_FOR_APPROVAL"
    assert "DROP INDEX CONCURRENTLY" in res["deployment_plan"]["rollback_command"]


def test_simulation_graph_blocks_candidate_violating_policy():
    bad_candidate = {
        **_fixture_candidate(),
        "regression_rate": 0.20,  # 20% regression > 5% threshold
        "p95_improvement_ratio": -0.05,  # Regression
    }
    report = run_simulation(bad_candidate)

    assert report["policy_verdict"] == "BLOCK"
    assert report["overall_status"] == "REJECTED"
    assert report["canary_eligible"] is False
    assert report["deployment_plan"]["status"] == "BLOCKED"
    assert len(report["violated_rules"]) > 0


def test_simulation_graph_blocks_on_high_skeptic_adversarial_score():
    risky_candidate = {
        **_fixture_candidate(),
        "skeptic_score": 0.75,  # High adversarial risk > 0.40
    }
    report = run_simulation(risky_candidate)

    assert report["policy_verdict"] == "BLOCK"
    assert report["canary_eligible"] is False
    assert any("Skeptic" in rule for rule in report["violated_rules"])


def test_simulation_graph_flags_underpowered_sample_size():
    underpowered = {
        **_fixture_candidate(),
        "sample_size": 3,
    }
    report = run_simulation(underpowered)

    assert report["statistical_verdict"] == "CONDITIONAL"
    assert report["policy_verdict"] == "CONDITIONAL"
    assert report["canary_eligible"] is False
