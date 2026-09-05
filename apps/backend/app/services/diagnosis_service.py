"""Application service for Feature 1 diagnosis investigations.

This module owns the application-database transaction around an investigation.
Customer-database access remains inside the read-only introspection boundary
used by the graph; this service only reads normalized telemetry snapshots.
"""

from __future__ import annotations

import uuid
import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.graph_diagnosis import run_diagnosis as run_agent_graph
from app.core.logging import get_logger
from app.db.customer_db import customer_connection_manager
from app.models.connection import DatabaseConnection
from app.models.diagnosis import Diagnosis, EvidenceGraphEdge, EvidenceGraphNode
from app.models.telemetry import PlanMetric, QueryMetric, TableMetric
from app.services.evidence_engine import calculate_cardinality_error, diff_plans
from app.tools import pg_introspection

logger = get_logger(__name__)


def _row(model: Any) -> dict[str, Any]:
    """Convert an ORM telemetry row to the graph's stable mapping contract."""
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _plan_hash(features: dict[str, Any]) -> str:
    material = "|".join(
        str(features.get(key, ""))
        for key in ("node_types", "join_types", "estimated_cost", "parallel_workers")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:64]


def _query_evidence(queries: list[QueryMetric], plans: list[PlanMetric], tables: list[TableMetric]) -> dict[str, Any]:
    plan_by_query: dict[uuid.UUID, list[PlanMetric]] = {}
    for plan in plans:
        if plan.query_metrics_id:
            plan_by_query.setdefault(plan.query_metrics_id, []).append(plan)

    query_rows: list[dict[str, Any]] = []
    for query in queries:
        row = _row(query)
        query_plans = sorted(plan_by_query.get(query.id, []), key=lambda item: item.timestamp)
        if query_plans:
            current = _row(query_plans[-1])
            row.update(current)
            row["cardinality_error"] = calculate_cardinality_error(current["estimated_rows"], current["actual_rows"])
            if len(query_plans) > 1:
                row.update(diff_plans(_row(query_plans[-2]), current))
        row["latency_p95"] = query.max_exec_time
        row["temp_io"] = query.temp_blks_read + query.temp_blks_written
        row["wal_rate"] = query.wal_bytes
        query_rows.append(_json_safe(row))

    table_rows = []
    for table in tables:
        row = _row(table)
        row["idx_scan_ratio"] = table.idx_scans / max(table.idx_scans + table.seq_scans, 1)
        table_rows.append(_json_safe(row))

    # The graph expects one feature mapping. Preserve the strongest observed
    # signal for every feature so a vacuum signal is not hidden by query I/O.
    metrics: dict[str, Any] = {}
    for item in [*query_rows, *table_rows]:
        for key, value in item.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[key] = max(float(value), float(metrics.get(key, 0.0)))
            elif key not in metrics and value is not None:
                metrics[key] = value
    timeline = [
        {"timestamp": item["timestamp"], "event": "query_telemetry", "query_hash": item.get("query_hash")}
        for item in query_rows
    ]
    return {
        "metrics": metrics,
        "query_metrics": query_rows,
        "table_metrics": table_rows,
        "plan_metrics": [_json_safe(_row(plan)) for plan in plans],
        "timeline": timeline,
    }


async def _load_evidence(
    connection_id: uuid.UUID,
    db: AsyncSession,
    *,
    time_window_minutes: int,
    query_id: int | None,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
    query_stmt = select(QueryMetric).where(QueryMetric.connection_id == connection_id, QueryMetric.timestamp >= cutoff)
    if query_id is not None:
        query_stmt = query_stmt.where(QueryMetric.queryid == query_id)
    query_stmt = query_stmt.order_by(QueryMetric.timestamp.desc()).limit(500)
    table_stmt = select(TableMetric).where(TableMetric.connection_id == connection_id, TableMetric.timestamp >= cutoff).order_by(TableMetric.timestamp.desc()).limit(500)
    plan_stmt = select(PlanMetric).where(PlanMetric.connection_id == connection_id, PlanMetric.timestamp >= cutoff).order_by(PlanMetric.timestamp.desc()).limit(1000)
    queries, tables, plans = await db.scalars(query_stmt), await db.scalars(table_stmt), await db.scalars(plan_stmt)
    return _query_evidence(list(queries), list(plans), list(tables))


def _age_hours(value: Any, now: datetime) -> float | None:
    if value is None:
        return None
    timestamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max(0.0, (now - timestamp).total_seconds() / 3600)


def _lock_waiters(
    activity: list[dict[str, Any]],
    locks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return actual lock waits, excluding normal client/background waits."""
    blocked_pids = {
        row.get("pid")
        for row in locks
        if row.get("granted") is False and row.get("pid") is not None
    }
    return [
        row
        for row in activity
        if str(row.get("wait_event_type") or "").lower() == "lock"
        or row.get("pid") in blocked_pids
    ]


def _plan_eligible(query: str) -> bool:
    normalized = query.strip().lower()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    return (
        (normalized.startswith("select") or normalized.startswith("with"))
        and ";" not in normalized
        and "$" not in normalized
        and "neon.neon_perf_counters" not in normalized
        and "pg_ls_dir" not in normalized
    )


async def _load_live_evidence(
    connection_id: uuid.UUID,
    db: AsyncSession,
    *,
    time_window_minutes: int,
    query_id: int | None,
) -> dict[str, Any]:
    """Read one diagnosis snapshot directly from the monitored PostgreSQL target."""
    connection = await db.scalar(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    if connection is None:
        raise LookupError("Connection not found")

    # A diagnosis must be based on the current monitored database.  The
    # application database is telemetry history, not a substitute for a
    # failed target connection.  Optional views can fail independently (for
    # example, a hosted provider may restrict pg_stat_wal), so retain those
    # failures as evidence and continue with the sources that are available.
    pool = await customer_connection_manager.get_customer_pool(connection_id, db)
    captured_at = datetime.now(timezone.utc)
    capture_errors: list[dict[str, str]] = []

    async with pool.acquire() as customer:
        async def capture(name: str, function: Any, default: Any) -> Any:
            try:
                return await function(customer)
            except Exception as exc:
                logger.warning(
                    "Live telemetry source unavailable",
                    extra={"connection_id": str(connection_id), "source": name, "error": str(exc)},
                )
                capture_errors.append({"source": name, "error": str(exc)})
                return default

        queries = await capture("pg_stat_statements", lambda conn: pg_introspection.get_query_metrics(conn, limit=500), [])
        tables = await capture("pg_stat_user_tables", pg_introspection.get_table_stats, [])
        activity = await capture("pg_stat_activity", pg_introspection.get_pg_activity, [])
        locks = await capture("pg_locks", pg_introspection.get_pg_locks, [])
        buffer_rows = await capture("pg_statio_user_tables", pg_introspection.get_buffer_stats, [])
        wal_stats = await capture("pg_stat_wal", pg_introspection.get_wal_stats, {})

        plan_metrics: list[dict[str, Any]] = []
        plan_errors: list[dict[str, Any]] = []
        for row in queries[:10]:
            query_text = str(row.get("query") or "")
            if not _plan_eligible(query_text):
                continue
            try:
                features = await pg_introspection.get_explain_plan(customer, query_text)
            except Exception as exc:
                plan_errors.append(
                    {
                        "query_hash": hashlib.sha256(query_text.encode("utf-8")).hexdigest()[:64],
                        "error": str(exc),
                        "timestamp": captured_at,
                    }
                )
                continue
            plan_metrics.append(
                _json_safe(
                    {
                        **features,
                        "query_text": query_text,
                        "query_id": row.get("queryid"),
                        "query_hash": hashlib.sha256(query_text.encode("utf-8")).hexdigest()[:64],
                        "plan_hash": _plan_hash(features),
                        "timestamp": captured_at,
                    }
                )
            )

    plan_flips: list[dict[str, Any]] = []
    for plan in plan_metrics:
        query_id_value = plan.get("query_id")
        if query_id_value is None:
            continue
        previous = await db.scalar(
            select(PlanMetric)
            .where(
                PlanMetric.connection_id == connection_id,
                PlanMetric.query_id == query_id_value,
            )
            .order_by(PlanMetric.timestamp.desc())
        )
        if previous and previous.plan_hash != plan.get("plan_hash"):
            plan_flips.append(
                {
                    "query_id": query_id_value,
                    "query_hash": plan.get("query_hash"),
                    "previous_plan_hash": previous.plan_hash,
                    "current_plan_hash": plan.get("plan_hash"),
                    "timestamp": captured_at,
                }
            )

    if query_id is not None:
        queries = [row for row in queries if row.get("queryid") == query_id]

    query_metrics: list[dict[str, Any]] = []
    for row in queries:
        query_text = str(row.get("query") or "")
        query_metrics.append(
            _json_safe(
                {
                    **row,
                    "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{connection_id}:query:{row.get('queryid')}"),
                    "connection_id": connection_id,
                    "timestamp": captured_at,
                    "query_hash": hashlib.sha256(query_text.encode("utf-8")).hexdigest()[:64],
                    "latency_p95": float(row.get("max_exec_time") or 0),
                    "temp_io": int(row.get("temp_blks_read") or 0) + int(row.get("temp_blks_written") or 0),
                    "wal_rate": int(row.get("wal_bytes") or 0),
                }
            )
        )

    history_cutoff = captured_at - timedelta(minutes=time_window_minutes)
    history_stmt = (
        select(QueryMetric)
        .where(
            QueryMetric.connection_id == connection_id,
            QueryMetric.timestamp >= history_cutoff,
            QueryMetric.capture_source == "live_postgresql",
        )
        .order_by(QueryMetric.timestamp.asc())
        .limit(1000)
    )
    if query_id is not None:
        history_stmt = history_stmt.where(QueryMetric.queryid == query_id)
    history_records = (await db.scalars(history_stmt)).all()
    temporal_window = [
        {
            **_row(metric),
            "latency_p50": metric.mean_exec_time,
            "latency_p95": metric.max_exec_time,
            "execution_time": metric.mean_exec_time,
            "buffer_hits": metric.shared_blks_hit,
            "buffer_reads": metric.shared_blks_read,
            "wal_rate": metric.wal_bytes,
            "timestamp": metric.timestamp,
        }
        for metric in history_records
    ]
    temporal_window.extend(query_metrics)

    table_metrics: list[dict[str, Any]] = []
    for row in tables:
        live = int(row.get("n_live_tup") or 0)
        dead = int(row.get("n_dead_tup") or 0)
        scans = int(row.get("seq_scan") or 0) + int(row.get("idx_scan") or 0)
        table_metrics.append(
            _json_safe(
                {
                    **row,
                    "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{connection_id}:table:{row.get('schemaname')}:{row.get('relname')}"),
                    "connection_id": connection_id,
                    "timestamp": captured_at,
                    "schema_name": row.get("schemaname") or "public",
                    "table_name": row.get("relname") or "unknown",
                    "live_tuples": live,
                    "dead_tuples": dead,
                    "dead_tuple_ratio": dead / max(live + dead, 1),
                    "idx_scan_ratio": int(row.get("idx_scan") or 0) / max(scans, 1),
                    "seq_scan_ratio": int(row.get("seq_scan") or 0) / max(scans, 1),
                    "analyze_age": _age_hours(row.get("last_analyze") or row.get("last_autoanalyze"), captured_at),
                    "vacuum_age": _age_hours(row.get("last_vacuum") or row.get("last_autovacuum"), captured_at),
                }
            )
        )

    lock_graph = pg_introspection.build_lock_graph(locks)
    waiting = _lock_waiters(activity, locks)
    temp_io = sum(int(row.get("temp_io") or 0) for row in query_metrics)
    buffer_reads = sum(int(row.get("heap_blks_read") or 0) for row in buffer_rows)
    buffer_hits = sum(int(row.get("heap_blks_hit") or 0) for row in buffer_rows)
    cardinality_errors = [
        calculate_cardinality_error(row.get("estimated_rows"), row.get("actual_rows"))
        for row in plan_metrics
    ]
    numeric_metrics: dict[str, Any] = {
        "query_count": len(query_metrics),
        "connection_count": len(activity),
        "lock_wait_count": len(waiting),
        "lock_wait_seconds": max(
            ((_age_hours(row.get("query_start"), captured_at) or 0) * 3600 for row in waiting),
            default=0,
        ),
        "temp_io": temp_io,
        "buffer_read_ratio": buffer_reads / max(buffer_reads + buffer_hits, 1),
        "wal_bytes": int(wal_stats.get("wal_bytes") or 0),
        "plan_count": len(plan_metrics),
        "plan_flip": len(plan_flips),
        "telemetry_capture_error_count": len(capture_errors),
    }
    latency_p50_values = sorted(float(row.get("mean_exec_time") or 0) for row in queries)
    latency_p95_values = sorted(float(row.get("max_exec_time") or 0) for row in queries)
    numeric_metrics.update(
        {
            "latency_p50": latency_p50_values[len(latency_p50_values) // 2] if latency_p50_values else 0.0,
            "latency_p95": latency_p95_values[
                min(len(latency_p95_values) - 1, math.ceil(len(latency_p95_values) * 0.95) - 1)
            ] if latency_p95_values else 0.0,
            "execution_time": sum(float(row.get("total_exec_time") or 0) for row in queries),
            "planning_time": sum(float(row.get("planning_time") or 0) for row in queries),
            "buffer_hits": sum(int(row.get("shared_blks_hit") or 0) for row in queries),
            "buffer_reads": sum(int(row.get("shared_blks_read") or 0) for row in queries),
            "temp_blks_read": sum(int(row.get("temp_blks_read") or 0) for row in queries),
            "temp_blks_written": sum(int(row.get("temp_blks_written") or 0) for row in queries),
            "wal_rate": int(sum(int(row.get("wal_bytes") or 0) for row in queries)),
        }
    )
    numeric_metrics["cache_hit_ratio"] = numeric_metrics["buffer_hits"] / max(
        numeric_metrics["buffer_hits"] + numeric_metrics["buffer_reads"], 1
    )
    positive_cardinality_errors = [value for value in cardinality_errors if value > 0]
    if positive_cardinality_errors:
        numeric_metrics["cardinality_error"] = max(positive_cardinality_errors)
    if any(
        "Seq Scan" in (node_type or "") and float(plan.get("actual_rows") or 0) >= 1000
        for plan in plan_metrics
        for node_type in plan.get("node_types", [])
    ):
        numeric_metrics["missing_index"] = 1
    if len(activity) > 50:
        numeric_metrics["connection_saturation"] = len(activity)
    if table_metrics:
        table_for_analyze = max(
            (row for row in table_metrics if row.get("analyze_age") is not None),
            key=lambda row: float(row.get("analyze_age") or 0.0),
            default=None,
        )
        table_for_vacuum = max(
            (row for row in table_metrics if row.get("vacuum_age") is not None),
            key=lambda row: float(row.get("vacuum_age") or 0.0),
            default=None,
        )
        numeric_metrics.update(
            {
                "dead_tuple_ratio": max(float(row["dead_tuple_ratio"]) for row in table_metrics),
                "seq_scan_ratio": max(float(row["seq_scan_ratio"]) for row in table_metrics),
                "affected_table": (
                    table_for_analyze.get("table_name") if table_for_analyze else
                    table_for_vacuum.get("table_name") if table_for_vacuum else
                    table_metrics[0].get("table_name")
                ),
            }
        )
        analyze_ages = [row["analyze_age"] for row in table_metrics if row["analyze_age"] is not None]
        vacuum_ages = [row["vacuum_age"] for row in table_metrics if row["vacuum_age"] is not None]
        if analyze_ages:
            numeric_metrics["analyze_age"] = max(analyze_ages)
        if vacuum_ages:
            numeric_metrics["vacuum_age"] = max(vacuum_ages)

    timeline = [
        {
            "timestamp": row["timestamp"],
            "event": "query_telemetry",
            "query_hash": row.get("query_hash"),
            "latency_ms": row.get("latency_p95"),
        }
        for row in query_metrics[:50]
    ]
    if lock_graph:
        timeline.append({"timestamp": captured_at, "event": "lock_contention", "lock_count": len(lock_graph)})
    timeline.extend(
        {"timestamp": flip["timestamp"], "event": "plan_flip", "query_hash": flip["query_hash"]}
        for flip in plan_flips
    )
    timeline.extend(
        {"timestamp": error["timestamp"], "event": "plan_capture_failed", "query_hash": error["query_hash"], "detail": error["error"]}
        for error in plan_errors
    )
    timeline.extend(
        {"timestamp": captured_at, "event": "telemetry_capture_failed", "source": error["source"], "detail": error["error"]}
        for error in capture_errors
    )

    return {
        "metrics": numeric_metrics,
        "query_metrics": query_metrics,
        "table_metrics": table_metrics,
        "plan_metrics": plan_metrics,
        "plan_flips": plan_flips,
        "plan_errors": plan_errors,
        "capture_errors": capture_errors,
        "temporal_window": [_json_safe(row) for row in temporal_window[-1000:]],
        "lock_graph": lock_graph,
        "timeline": timeline,
        "source": "live_postgresql",
        "captured_at": captured_at,
        "time_window_minutes": time_window_minutes,
    }


def _persist_graph(diagnosis: Diagnosis, report: dict[str, Any]) -> None:
    root = EvidenceGraphNode(
        node_key="root-cause",
        node_type="ROOT_CAUSE",
        label=str(report.get("primary_root_cause", "UNKNOWN")),
        agent_domain="SUPERVISOR",
        confidence=float(report.get("confidence", 0.0)),
        metadata_payload={"summary": report.get("summary"), "hypotheses": _json_safe(report.get("hypotheses", []))},
    )
    diagnosis.nodes.append(root)
    for index, hypothesis in enumerate(report.get("hypotheses", [])):
        agent = str(hypothesis.get("agent", "UNKNOWN"))
        if str(hypothesis.get("cause", "UNKNOWN")).upper() == "UNKNOWN":
            continue
        node = EvidenceGraphNode(
            node_key=f"hypothesis-{index}",
            node_type="HYPOTHESIS",
            label=str(hypothesis.get("cause", "UNKNOWN")),
            agent_domain=agent,
            confidence=float(hypothesis.get("confidence", 0.0)),
            metadata_payload={"evidence": _json_safe(hypothesis.get("evidence", []))},
        )
        diagnosis.nodes.append(node)
        diagnosis.edges.append(EvidenceGraphEdge(
            source_node=node,
            target_node=root,
            relation_type="CAUSES" if node.label == root.label else "CORRELATES_WITH",
            weight=float(node.confidence),
            explanation="Specialist hypothesis reconciled by the supervisor.",
        ))

    for index, evidence in enumerate(report.get("evidence", [])):
        payload = _json_safe(evidence if isinstance(evidence, dict) else {"claim": str(evidence)})
        node = EvidenceGraphNode(
            node_key=f"evidence-{index}",
            node_type="METRIC" if "metric" in payload else "EVENT",
            label=str(payload.get("claim", payload.get("metric", "evidence"))),
            agent_domain=str(payload.get("source", "SUPERVISOR")),
            confidence=float(payload.get("directness", 1.0)),
            metadata_payload=payload,
        )
        diagnosis.nodes.append(node)
        diagnosis.edges.append(EvidenceGraphEdge(
            source_node=node,
            target_node=root,
            relation_type="CAUSES" if float(payload.get("directness", 0.0)) >= 0.8 else "CORRELATES_WITH",
            weight=float(payload.get("directness", 0.0)),
            explanation="Evidence item supporting the persisted diagnosis.",
        ))

    models = report.get("models", {})
    model_nodes = [
        (
            "model-anomaly",
            "MODEL_ANOMALY",
            "Isolation Forest anomaly score",
            models.get("anomaly", {}).get("anomaly_score"),
            models.get("anomaly", {}),
        ),
        (
            "model-temporal",
            "MODEL_TEMPORAL",
            "Temporal LSTM anomaly probability",
            models.get("temporal", {}).get("anomaly_probability"),
            models.get("temporal", {}),
        ),
    ]
    ranked_causes = models.get("rca", {}).get("ranked_causes", [])
    if ranked_causes:
        top_cause = ranked_causes[0]
        model_nodes.append(
            (
                "model-rca",
                "MODEL_RCA",
                f"RCA classifier: {top_cause.get('cause', 'UNKNOWN')}",
                top_cause.get("probability"),
                top_cause,
            )
        )
    for node_key, node_type, label, confidence, metadata in model_nodes:
        if confidence is None:
            continue
        node = EvidenceGraphNode(
            node_key=node_key,
            node_type=node_type,
            label=label,
            agent_domain="ML",
            confidence=max(0.0, min(float(confidence), 1.0)),
            metadata_payload=_json_safe(metadata),
        )
        diagnosis.nodes.append(node)
        diagnosis.edges.append(EvidenceGraphEdge(
            source_node=node,
            target_node=root,
            relation_type="CORRELATES_WITH",
            weight=node.confidence,
            explanation="Model output evaluated against the live telemetry snapshot.",
        ))


async def run_diagnosis(
    connection_id: uuid.UUID,
    db: AsyncSession,
    *,
    time_window_minutes: int = 60,
    query_id: int | None = None,
    customer_connection: Any = None,
) -> Diagnosis:
    """Run, persist, and return one complete diagnosis for a connection."""
    if time_window_minutes < 5 or time_window_minutes > 1440:
        raise ValueError("time_window_minutes must be between 5 and 1440")
    connection = await db.scalar(select(DatabaseConnection).where(DatabaseConnection.id == connection_id))
    if connection is None:
        raise LookupError("Connection not found")

    evidence = await _load_live_evidence(
        connection_id,
        db,
        time_window_minutes=time_window_minutes,
        query_id=query_id,
    )
    try:
        report = run_agent_graph(evidence, connection=customer_connection)
        diagnosis = Diagnosis(
            connection_id=connection_id,
            title=str(report.get("title", "Database diagnosis")),
            primary_root_cause=str(report.get("primary_root_cause", "UNKNOWN")),
            contributing_factors=_json_safe(report.get("contributing_factors", report.get("contributing_causes", []))),
            severity=str(report.get("severity", "LOW")),
            confidence=max(0.0, min(float(report.get("confidence", 0.0)), 1.0)),
            summary=str(report.get("summary", "No diagnosis summary available.")),
            validation_plan=_json_safe(
                {
                    **report.get("validation_plan", {}),
                    "source": evidence.get("source"),
                    "captured_at": evidence.get("captured_at"),
                    "capture_errors": evidence.get("capture_errors", []),
                    "plan_errors": evidence.get("plan_errors", []),
                    "model_outputs": report.get("models", {}),
                    "time_window_minutes": time_window_minutes,
                    "timeline": report.get("timeline", []),
                    "supporting_evidence": report.get("evidence", []),
                    "recommended_action": report.get("recommended_action"),
                    "affected_object": (
                        report.get("evidence", [{}])[0].get("table_name") or "database"
                        if report.get("evidence") and isinstance(report.get("evidence", [{}])[0], dict)
                        else "database"
                    ),
                }
            ),
            status=str(report.get("status", "DETECTED")),
        )
        _persist_graph(diagnosis, report)
        db.add(diagnosis)

        # Audit log the diagnosis creation event per PRD.md §14, §15
        from app.models.audit import AuditLog
        from app.core.logging import log_agent_execution
        
        audit_entry = AuditLog(
            connection_id=connection_id,
            action_type="DIAGNOSIS_GENERATED",
            target_entity="diagnosis",
            target_id=str(diagnosis.id),
            details={
                "title": diagnosis.title,
                "primary_root_cause": diagnosis.primary_root_cause,
                "severity": diagnosis.severity,
                "confidence": diagnosis.confidence,
                "node_count": len(diagnosis.nodes),
            },
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_entry)

        log_agent_execution(
            agent_name="SupervisorAgent",
            action="DIAGNOSIS_GENERATED",
            evidence={"root_cause": diagnosis.primary_root_cause, "nodes": len(diagnosis.nodes)},
            confidence=diagnosis.confidence,
            connection_id=str(connection_id),
        )

        await db.commit()
        persisted = await db.scalar(
            select(Diagnosis)
            .where(Diagnosis.id == diagnosis.id)
            .options(selectinload(Diagnosis.nodes), selectinload(Diagnosis.edges))
        )
        return persisted or diagnosis
    except Exception:
        await db.rollback()
        raise


class DiagnosisService:
    """Named service facade used by API routes and background workers."""

    async def run_diagnosis(self, connection_id: uuid.UUID, db: AsyncSession, **kwargs: Any) -> Diagnosis:
        return await run_diagnosis(connection_id, db, **kwargs)


diagnosis_service = DiagnosisService()
