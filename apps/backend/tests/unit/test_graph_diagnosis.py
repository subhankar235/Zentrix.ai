from app.agents.graph_diagnosis import DOMAINS, TOOL_SUBSETS, diagnosis_graph, run_diagnosis
from app.agents.llm_client import LLMClient


def _fixture():
    return {
        "timeline": [{"timestamp": "2026-08-21T10:00:00Z", "event": "bulk load"}],
        "hypotheses": {
            "PLANNER": {"cause": "STALE_STATISTICS", "confidence": 0.91, "evidence": [{"claim": "stats age 48h", "timestamp": "2026-08-21T10:01:00Z", "directness": 1.0}]},
            "CONCURRENCY": {"cause": "LOCK_CONTENTION", "confidence": 0.42, "evidence": ["one short wait"]},
            "VACUUM": {"cause": "VACUUM_LAG", "confidence": 0.35, "evidence": ["dead tuples rising"]},
            "IO_BUFFER": {"cause": "BUFFER_PRESSURE", "confidence": 0.3, "evidence": ["read blocks rising"]},
            "SCHEMA_INDEX": {"cause": "INDEX_UNUSED", "confidence": 0.2, "evidence": ["index scan ratio low"]},
        },
    }


def test_graph_runs_all_specialists_and_scopes_tools():
    result = diagnosis_graph.invoke({"evidence": _fixture()})
    specialists = result["specialists"]

    assert {item["agent"] for item in specialists} == set(DOMAINS)
    assert all(item["hypothesis"] and 0 <= item["confidence"] <= 1 for item in specialists)
    assert {item["agent"]: item["tools"] for item in specialists} == TOOL_SUBSETS


def test_supervisor_report_has_prd_shape_and_picks_strongest_direct_evidence():
    report = run_diagnosis(_fixture())

    assert report["primary_root_cause"] == "STALE_STATISTICS"
    assert report["confidence"] == 0.91
    assert report["evidence"]
    assert report["timeline"]
    assert report["validation_plan"]["counterfactual_required"] is True
    assert report["hypotheses"]
    assert report["recommended_action"]


def test_unresolved_contradiction_is_unknown_and_preserves_hypotheses():
    evidence = {"hypotheses": {domain: {"cause": cause, "confidence": 0.8, "evidence": [{"claim": cause, "directness": 0.5}]} for domain, cause in zip(DOMAINS[:2], ("PLAN_FLIP", "LOCK_CONTENTION"))}}
    report = run_diagnosis(evidence)

    assert report["primary_root_cause"] == "UNKNOWN"
    assert {item["cause"] for item in report["hypotheses"] if item["cause"] != "UNKNOWN"} == {"PLAN_FLIP", "LOCK_CONTENTION"}


def test_llm_client_supports_injected_plain_and_structured_completion():
    client = LLMClient(lambda prompt, **_: '{"answer": 42}')
    assert client.complete("prompt") == '{"answer": 42}'
    assert client.structured_complete("return JSON") == {"answer": 42}
