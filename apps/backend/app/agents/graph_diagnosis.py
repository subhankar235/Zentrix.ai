"""Evidence-first LangGraph for Feature 1 root-cause diagnosis."""

from __future__ import annotations

import inspect
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Mapping, Sequence
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.llm_client import LLMClient, get_llm_client
from app.ml.anomaly.predict import predict as predict_anomaly
from app.ml.diagnosis_models import ensure_feature1_models, model_paths
from app.ml.rca_classifier.predict import predict as predict_rca
from app.ml.temporal.features import build_windows
from app.ml.temporal.predict import predict as predict_temporal
from app.tools import pg_introspection


DOMAINS = ("PLANNER", "CONCURRENCY", "VACUUM", "IO_BUFFER", "SCHEMA_INDEX")
TOOL_SUBSETS = {
    "PLANNER": ("get_explain_plan", "get_plan_history", "get_pg_stats", "get_table_statistics", "compare_plan", "calculate_cardinality_error"),
    "CONCURRENCY": ("get_pg_activity", "get_pg_locks", "get_wait_events", "build_lock_graph"),
    "VACUUM": ("get_table_stats", "get_vacuum_progress", "get_autovacuum_history", "estimate_bloat", "get_dead_tuple_ratio"),
    "IO_BUFFER": ("get_buffer_stats", "get_io_stats", "get_explain_buffers", "get_temp_file_stats", "get_wal_stats"),
    "SCHEMA_INDEX": ("get_indexes", "get_index_usage", "get_table_schema", "get_constraints", "get_query_plan"),
}


class DiagnosisState(TypedDict, total=False):
    evidence: dict[str, Any]
    specialists: Annotated[list[dict[str, Any]], add]
    report: dict[str, Any]
    connection: Any
    llm_client: LLMClient
    models: dict[str, Any]


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, Mapping)) else [value]


def _evidence(item: Any, domain: str) -> dict[str, Any]:
    if isinstance(item, Mapping):
        result = dict(item)
        result.setdefault("source", domain)
        result.setdefault("directness", 1.0)
        return result
    return {"claim": str(item), "source": domain, "directness": 1.0}


def _domain_signal(domain: str, evidence: Mapping[str, Any]) -> tuple[str, float, list[dict[str, Any]]]:
    """Use explicit fixture signals first, then conservative metric heuristics."""
    configured = evidence.get("hypotheses", {}).get(domain) if isinstance(evidence.get("hypotheses"), Mapping) else None
    if isinstance(configured, Mapping):
        cause = str(configured.get("cause", "UNKNOWN")).upper()
        confidence = float(configured.get("confidence", 0.0))
        items = [_evidence(item, domain) for item in _as_items(configured.get("evidence"))]
        return cause, max(0.0, min(confidence, 1.0)), items

    metrics = evidence.get("metrics", evidence)
    if not isinstance(metrics, Mapping):
        metrics = {}
    if domain == "SCHEMA_INDEX":
        plans = evidence.get("plan_metrics", [])
        for plan in plans if isinstance(plans, Sequence) else []:
            node_types = plan.get("node_types", []) if isinstance(plan, Mapping) else []
            actual_rows = float(plan.get("actual_rows") or 0) if isinstance(plan, Mapping) else 0
            if any("Seq Scan" in str(node_type) for node_type in _as_items(node_types)) and actual_rows >= 1000:
                return "INDEX_MISSING", 0.9, [
                    _evidence(
                        {
                            "claim": "Live EXPLAIN reported a sequential scan over a large result set.",
                            "metric": "actual_rows",
                            "value": actual_rows,
                            "query_hash": plan.get("query_hash"),
                            "query_text": plan.get("query_text"),
                            "table_name": plan.get("table_name"),
                        },
                        domain,
                    )
                ]

    rules = {
        "PLANNER": (("plan_flip", "PLAN_FLIP"), ("cardinality_error", "CARDINALITY_MISESTIMATION"), ("analyze_age", "STALE_STATISTICS")),
        "CONCURRENCY": (("lock_wait_seconds", "LOCK_CONTENTION"), ("lock_wait_count", "LOCK_CONTENTION"), ("connection_saturation", "CONNECTION_CONTENTION")),
        "VACUUM": (("dead_tuple_ratio", "BLOAT"), ("vacuum_age", "VACUUM_LAG")),
        # WAL bytes are cumulative counters, not a rate without two snapshots;
        # do not diagnose checkpoint pressure from one live sample.
        "IO_BUFFER": (("temp_io", "TEMP_SPILL"), ("buffer_read_ratio", "BUFFER_PRESSURE")),
        "SCHEMA_INDEX": (("missing_index", "INDEX_MISSING"),),
    }
    for key, cause in rules[domain]:
        value = metrics.get(key)
        if value is not None and float(value) > (0.0 if key in {"plan_flip", "missing_index"} else 0.5):
            confidence = min(0.95, 0.55 + abs(float(value)) / 10)
            return cause, confidence, [_evidence({"metric": key, "value": value}, domain)]
    return "UNKNOWN", 0.0, []


async def _call_tools(domain: str, state: DiagnosisState) -> dict[str, Any]:
    connection = state.get("connection")
    requested = state.get("evidence", {}).get("tool_results", {})
    results = dict(requested) if isinstance(requested, Mapping) else {}
    if connection is None:
        return results
    arguments = state.get("evidence", {}).get("tool_arguments", {})
    for name in TOOL_SUBSETS[domain]:
        if name in results or not hasattr(pg_introspection, name):
            continue
        function = getattr(pg_introspection, name)
        args = arguments.get(name, []) if isinstance(arguments, Mapping) else []
        result = function(connection, *args)
        results[name] = await result if inspect.isawaitable(result) else result
    return results


def _ml_context(evidence: Mapping[str, Any]) -> dict[str, Any]:
    metrics = evidence.get("metrics", evidence)
    return dict(metrics) if isinstance(metrics, Mapping) else {}


def _predict_models(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Run all Feature 1 models once for the current live evidence snapshot."""
    if evidence.get("source") != "live_postgresql" and not evidence.get("enable_ml"):
        return {}

    artifacts = ensure_feature1_models()
    paths = model_paths()
    context = _ml_context(evidence)
    results: dict[str, Any] = {"artifacts": artifacts}
    for label, function, path in (
        ("rca", predict_rca, paths["rca"]),
        ("anomaly", predict_anomaly, paths["anomaly"]),
    ):
        if not path.is_file():
            results[label] = {
                "status": "unavailable",
                "reason": "A promoted model artifact is required; no training data was generated.",
            }
            continue
        try:
            results[label] = function(context, path)
        except Exception as exc:
            results[label] = {"status": "error", "error": str(exc)}

    temporal_rows = evidence.get("temporal_window", [])
    distinct_timestamps = {str(row.get("timestamp")) for row in temporal_rows if isinstance(row, Mapping)}
    windows = (
        build_windows(temporal_rows, window_size=30)
        if len(distinct_timestamps) >= 30
        else build_windows([], window_size=30)
    )
    if not paths["temporal"].is_file():
        results["temporal"] = {
            "status": "unavailable",
            "reason": "A promoted model artifact is required; no training data was generated.",
        }
    elif len(windows):
        try:
            results["temporal"] = predict_temporal(windows[-1], paths["temporal"])
        except Exception as exc:
            results["temporal"] = {"status": "error", "error": str(exc)}
    else:
        results["temporal"] = {
            "status": "insufficient_history",
            "required_rows": 30,
            "available_rows": len(distinct_timestamps),
        }
    return results


def _await_sync(awaitable: Any) -> Any:
    """Bridge async introspection tools for LangGraph's sync invoke API."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, awaitable).result()


def _specialist_node(domain: str):
    def node(state: DiagnosisState) -> dict[str, Any]:
        evidence = dict(state.get("evidence", {}))
        evidence["tool_results"] = _await_sync(_call_tools(domain, state))
        cause, confidence, items = _domain_signal(domain, evidence)
        return {"specialists": [{"agent": domain, "tools": list(TOOL_SUBSETS[domain]), "hypothesis": cause, "confidence": confidence, "evidence": items}]}
    return node


def _supervisor(state: DiagnosisState) -> dict[str, Any]:
    specialists = state.get("specialists", [])
    candidates = [item for item in specialists if item.get("hypothesis") not in (None, "UNKNOWN")]
    candidates.sort(key=lambda item: (-_directness(item), _earliest(item) or "9999", -float(item.get("confidence", 0))))
    primary = candidates[0] if candidates else None
    if primary and len(candidates) > 1:
        direct = sum(float(item.get("evidence", [{}])[0].get("directness", 0)) for item in candidates if item.get("evidence"))
        top_direct = float(primary.get("evidence", [{}])[0].get("directness", 0)) if primary.get("evidence") else 0
        tied = abs(float(primary.get("confidence", 0)) - float(candidates[1].get("confidence", 0))) < 0.05
        if tied and top_direct <= direct - top_direct:
            primary = None
    all_hypotheses = [{"agent": item.get("agent"), "cause": item.get("hypothesis"), "confidence": item.get("confidence"), "evidence": item.get("evidence", [])} for item in specialists]
    cause = primary.get("hypothesis", "UNKNOWN") if primary else "UNKNOWN"
    confidence = float(primary.get("confidence", 0.0)) if primary else 0.0
    evidence = primary.get("evidence", []) if primary else [e for item in specialists for e in item.get("evidence", [])]
    live_evidence = state.get("evidence", {})
    if not primary and live_evidence.get("source") == "live_postgresql":
        has_snapshot = any(
            live_evidence.get(key)
            for key in ("query_metrics", "table_metrics", "plan_metrics", "timeline")
        )
        capture_errors = live_evidence.get("capture_errors", [])
        plan_errors = live_evidence.get("plan_errors", [])
        has_non_plan_snapshot = bool(live_evidence.get("query_metrics") or live_evidence.get("table_metrics"))
        if has_snapshot and not capture_errors and (not plan_errors or has_non_plan_snapshot):
            cause = "NO_ACTIVE_INCIDENT"
            confidence = 0.85
            evidence = [
                _evidence(
                    {
                        "claim": "The live PostgreSQL snapshot contained no deterministic threshold breach.",
                        "metric": "captured_query_count",
                        "value": len(live_evidence.get("query_metrics", [])),
                        "table_count": len(live_evidence.get("table_metrics", [])),
                        "plan_count": len(live_evidence.get("plan_metrics", [])),
                        "directness": 1.0,
                    },
                    "LIVE_POSTGRESQL",
                )
            ]
        else:
            cause = "INSUFFICIENT_EVIDENCE"
            confidence = 0.1
            evidence = [
                _evidence(
                    {
                        "claim": "The live PostgreSQL snapshot did not contain enough diagnostic-grade evidence for a root-cause claim.",
                        "metric": "captured_query_count",
                        "value": len(live_evidence.get("query_metrics", [])),
                        "capture_errors": capture_errors,
                        "plan_errors": plan_errors,
                        "directness": 1.0,
                    },
                    "LIVE_POSTGRESQL",
                )
            ]
    contributing = [{"cause": item["hypothesis"], "confidence": item.get("confidence", 0.0), "agent": item.get("agent")} for item in candidates[1:] if item["hypothesis"] != cause]
    report = {
        "title": f"Database diagnosis: {cause}",
        "primary_root_cause": cause,
        "confidence": confidence,
        "severity": "HIGH" if confidence >= 0.75 and cause not in {"NO_ACTIVE_INCIDENT"} else "MEDIUM" if confidence >= 0.4 else "LOW",
        "contributing_causes": contributing,
        "contributing_factors": contributing,
        "evidence": evidence,
        "timeline": state.get("evidence", {}).get("timeline", []),
        "recommended_action": _recommendation(cause),
        "validation_plan": {"steps": _validation(cause), "counterfactual_required": True},
        "hypotheses": all_hypotheses,
        "models": state.get("models", {}),
        "summary": (
            "No active incident was found in the current live PostgreSQL snapshot."
            if cause == "NO_ACTIVE_INCIDENT"
            else "Live PostgreSQL evidence was insufficient for a root-cause claim."
            if cause == "INSUFFICIENT_EVIDENCE"
            else "UNKNOWN: specialist evidence was unresolved."
            if cause == "UNKNOWN"
            else f"{cause} is the earliest and best-supported explanation."
        ),
        "status": "OBSERVED" if cause == "NO_ACTIVE_INCIDENT" else "INSUFFICIENT_EVIDENCE" if cause == "INSUFFICIENT_EVIDENCE" else "DETECTED",
    }
    return {"report": report}


def _earliest(item: Mapping[str, Any]) -> str:
    evidence = item.get("evidence", [])
    return str(evidence[0].get("timestamp", "")) if evidence and isinstance(evidence[0], Mapping) else ""


def _directness(item: Mapping[str, Any]) -> float:
    evidence = item.get("evidence", [])
    if not evidence:
        return 0.0
    values = [float(entry.get("directness", 0.0)) for entry in evidence if isinstance(entry, Mapping)]
    return max(values, default=0.0)


def _recommendation(cause: str) -> str:
    return {"STALE_STATISTICS": "Run ANALYZE on the affected relation after validation.", "VACUUM_LAG": "Review autovacuum thresholds and vacuum the affected relation.", "LOCK_CONTENTION": "Identify and resolve the blocking transaction.", "INDEX_MISSING": "Validate a candidate index in a shadow environment.", "NO_ACTIVE_INCIDENT": "Continue collecting live telemetry; no corrective action is indicated.", "INSUFFICIENT_EVIDENCE": "Continue collecting live telemetry before taking corrective action.", "UNKNOWN": "Collect more telemetry before taking corrective action."}.get(cause, "Validate the hypothesis in a read-only or shadow environment.")


def _validation(cause: str) -> list[str]:
    if cause == "NO_ACTIVE_INCIDENT":
        return ["Continue the read-only telemetry collector and review the next timestamped snapshots."]
    if cause == "INSUFFICIENT_EVIDENCE":
        return ["Collect at least 30 timestamped live telemetry snapshots before evaluating temporal or trend-based causes."]
    return ["Re-run the affected read-only query with EXPLAIN (ANALYZE, BUFFERS).", f"Confirm that {cause} evidence is reduced after the controlled remediation."]


def build_diagnosis_graph() -> Any:
    graph = StateGraph(DiagnosisState)
    for domain in DOMAINS:
        graph.add_node(domain, _specialist_node(domain))
    graph.add_node("supervisor", _supervisor)
    graph.add_conditional_edges(START, _fanout)
    for domain in DOMAINS:
        graph.add_edge(domain, "supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile()


def _fanout(state: DiagnosisState) -> list[Send]:
    return [Send(domain, {**state, "specialists": []}) for domain in DOMAINS]


diagnosis_graph = build_diagnosis_graph()


def run_diagnosis(evidence: Mapping[str, Any], *, connection: Any = None, llm_client: LLMClient | None = None) -> dict[str, Any]:
    """Run the graph synchronously for a fixture or service call."""
    payload = dict(evidence)
    return diagnosis_graph.invoke(
        {
            "evidence": payload,
            "connection": connection,
            "llm_client": llm_client or get_llm_client(),
            "models": _predict_models(payload),
        }
    )["report"]
