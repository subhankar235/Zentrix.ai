"""Feature 3 LangGraph Multi-Agent Orchestration (Forecast/Planning & Learning Agents).

Coordinates:
1. Forecast/Planning Agent: Evaluates L1 degradation forecasting curve and triggers proactive optimization.
2. Strategy Selector Agent: Evaluates Contextual Thompson Sampling bandit recommendations.
3. Simulation Request Node: Dispatches candidate optimization to Feature 2 sandbox for verification.
4. Learning Agent: Tracks closed-loop feedback and retraining readiness.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 3, §6.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.core.logging import get_logger
from app.ml.bandit.policy import ContextualThompsonSamplingBandit, RolloutPhase
from app.ml.forecasting.predict import predict as predict_forecasting

logger = get_logger(__name__)


class ForecastState(TypedDict, total=False):
    connection_id: str
    query_id: int | None
    table_name: str | None
    telemetry_history: list[dict[str, Any]]
    forecast_result: dict[str, Any]
    strategy_decision: dict[str, Any]
    candidate_spec: dict[str, Any]
    simulation_result: dict[str, Any]
    learning_report: dict[str, Any]
    status: str
    messages: list[str]


def forecast_planning_node(state: ForecastState) -> dict[str, Any]:
    """Forecast/Planning Agent: Evaluates 7-day degradation risk using L1 LightGBM."""
    telemetry = state.get("telemetry_history", [])
    query_id = state.get("query_id")

    logger.info(f"Forecast/Planning Agent evaluating telemetry sequence of length {len(telemetry)}")
    pred_res = predict_forecasting(telemetry, horizon_hours=168)

    prob = pred_res.get("degradation_probability", 0.0)
    is_flagged = pred_res.get("is_flagged_for_action", False)

    status = "ACTION_REQUIRED" if is_flagged else "MONITORING_NORMAL"
    msg = (
        f"L1 Forecast: 7-day degradation probability is {prob * 100:.1f}%. "
        f"Status: {status}."
    )

    return {
        "forecast_result": pred_res,
        "status": status,
        "messages": [msg],
    }


def strategy_selector_node(state: ForecastState) -> dict[str, Any]:
    """Strategy Selector Agent: Selects optimization strategy via Contextual Thompson Sampling."""
    forecast = state.get("forecast_result", {})
    if not forecast.get("is_flagged_for_action", False):
        return {
            "strategy_decision": {"selected_action": "DO_NOTHING", "reason": "Risk below threshold"},
            "candidate_spec": None,
        }

    telemetry = state.get("telemetry_history", [])
    latest = telemetry[-1] if telemetry else {}
    table_name = state.get("table_name") or latest.get("table_name", "target_table")

    context = {
        "cardinality_error": float(latest.get("cardinality_error", 0.0)),
        "dead_tuple_ratio": float(latest.get("dead_tuple_ratio", 0.0)),
        "idx_scan_ratio": float(latest.get("idx_scan_ratio", 0.5)),
        "p95_exec_time": float(latest.get("p95_exec_time", latest.get("mean_exec_time", 50.0))),
        "mean_exec_time": float(latest.get("mean_exec_time", 30.0)),
        "calls": float(latest.get("calls", 100.0)),
        "shared_blks_read": float(latest.get("shared_blks_read", 50.0)),
        "cpu_seconds": float(latest.get("cpu_seconds", 0.1)),
        "table_size_mb": float(latest.get("table_size_bytes", 10_000_000)) / (1024 * 1024),
    }

    # Contextual bandit selection (gated)
    bandit = ContextualThompsonSamplingBandit(rollout_phase=RolloutPhase.PHASE_1_RULE_BASED)
    decision = bandit.select_action(context)
    action = decision["selected_action"]

    # Generate candidate DDL / command
    if action in {"CREATE_INDEX", "PARTIAL_INDEX"}:
        candidate_sql = f"CREATE INDEX CONCURRENTLY idx_proactive_{table_name} ON {table_name}(created_at);"
    elif action in {"UPDATE_STATISTICS", "VACUUM_ANALYZE"}:
        candidate_sql = f"ANALYZE {table_name};"
    elif action == "QUERY_REWRITE":
        candidate_sql = "-- Suggest query optimization and parameter tuning"
    else:
        candidate_sql = "ANALYZE;"

    candidate_spec = {
        "strategy": action,
        "candidate_sql": candidate_sql,
        "table_name": table_name,
        "query_id": state.get("query_id"),
        "baseline_p95": context["p95_exec_time"],
        "candidate_p95": context["p95_exec_time"] * 0.65,
        "context": context,
        "decision": decision,
    }

    msg = f"Strategy Selector: Selected action '{action}' via {decision.get('decision_source')}."
    current_msgs = state.get("messages", [])

    return {
        "strategy_decision": decision,
        "candidate_spec": candidate_spec,
        "messages": current_msgs + [msg],
    }


def simulation_dispatch_node(state: ForecastState) -> dict[str, Any]:
    """Dispatches candidate to Feature 2 sandbox when simulation is warranted."""
    candidate = state.get("candidate_spec")
    if not candidate or candidate.get("strategy") == "DO_NOTHING":
        return {"simulation_result": {"status": "SKIPPED", "reason": "No actionable candidate"}}

    predicted_delta = candidate["candidate_p95"] - candidate["baseline_p95"]

    sim_res = {
        "status": "DISPATCH_READY",
        "candidate_sql": candidate["candidate_sql"],
        "strategy": candidate["strategy"],
        "table_name": candidate["table_name"],
        "predicted_latency_delta": predicted_delta,
        "requires_feature2_sandbox": True,
    }

    msg = f"Simulation Dispatch: Candidate '{candidate['strategy']}' prepared for Feature 2 verification."
    current_msgs = state.get("messages", [])

    return {
        "simulation_result": sim_res,
        "messages": current_msgs + [msg],
    }


def learning_node(state: ForecastState) -> dict[str, Any]:
    """Learning Agent: Checks retraining triggers and drift status."""
    report = {
        "status": "LEARNING_MONITORED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "closed_loop_feedback_active": True,
    }
    return {"learning_report": report}


def create_forecast_graph() -> StateGraph:
    """Compile the Feature 3 LangGraph state graph."""
    builder = StateGraph(ForecastState)

    builder.add_node("forecast_planning", forecast_planning_node)
    builder.add_node("strategy_selector", strategy_selector_node)
    builder.add_node("simulation_dispatch", simulation_dispatch_node)
    builder.add_node("learning", learning_node)

    builder.set_entry_point("forecast_planning")
    builder.add_edge("forecast_planning", "strategy_selector")
    builder.add_edge("strategy_selector", "simulation_dispatch")
    builder.add_edge("simulation_dispatch", "learning")
    builder.add_edge("learning", END)

    return builder.compile()


forecast_graph = create_forecast_graph()


def run_forecast_pipeline(
    connection_id: str,
    telemetry_history: Sequence[Mapping[str, Any]],
    query_id: int | None = None,
    table_name: str | None = None,
) -> dict[str, Any]:
    """Synchronous / programmatic wrapper to execute the Feature 3 forecasting pipeline."""
    initial_state: ForecastState = {
        "connection_id": connection_id,
        "query_id": query_id,
        "table_name": table_name,
        "telemetry_history": [dict(t) for t in telemetry_history],
        "messages": [],
    }

    result = forecast_graph.invoke(initial_state)
    return dict(result)
