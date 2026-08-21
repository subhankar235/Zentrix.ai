"""Application service for Feature 1 diagnosis investigations.

This module owns the application-database transaction around an investigation.
Customer-database access remains inside the read-only introspection boundary
used by the graph; this service only reads normalized telemetry snapshots.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.graph_diagnosis import run_diagnosis as run_agent_graph
from app.models.connection import DatabaseConnection
from app.models.diagnosis import Diagnosis, EvidenceGraphEdge, EvidenceGraphNode
from app.models.telemetry import PlanMetric, QueryMetric, TableMetric
from app.services.evidence_engine import calculate_cardinality_error, diff_plans


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

    evidence = await _load_evidence(connection_id, db, time_window_minutes=time_window_minutes, query_id=query_id)
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
            validation_plan=_json_safe(report.get("validation_plan", {})),
            status=str(report.get("status", "DETECTED")),
        )
        _persist_graph(diagnosis, report)
        db.add(diagnosis)
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
